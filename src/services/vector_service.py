"""
Vector Service for semantic search using ChromaDB and sentence transformers.
Provides semantic similarity search for legal hypotheticals.
"""

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

# ── Python 3.14+ compatibility patch for pydantic v1 ──────────────────────────
# Python 3.14 changed how class-body annotations are stored: they are now
# accessed via __annotate_func__ (PEP 649) instead of being written directly
# into __annotations__ during class body execution.  Pydantic v1's
# ModelMetaclass.__new__ reads `namespace.get('__annotations__', {})`, which
# returns {} on 3.14, causing ConfigError for every annotated field.
# This patch evaluates __annotate_func__ and injects __annotations__ before
# pydantic v1 processes the namespace.
if sys.version_info >= (3, 14):
    try:
        import pydantic.v1.main as _pyd_main

        _orig_meta_new = _pyd_main.ModelMetaclass.__new__

        def _patched_meta_new(mcs, name, bases, namespace, **kwargs):
            if "__annotations__" not in namespace and "__annotate_func__" in namespace:
                annotate_func = namespace["__annotate_func__"]
                try:
                    import annotationlib

                    annotations = annotate_func(annotationlib.Format.VALUE)
                except Exception:
                    try:
                        annotations = annotate_func(1)  # Format.VALUE == 1
                    except Exception:
                        annotations = {}
                namespace["__annotations__"] = annotations
            return _orig_meta_new(mcs, name, bases, namespace, **kwargs)

        _pyd_main.ModelMetaclass.__new__ = _patched_meta_new
    except Exception:
        pass  # pydantic.v1 not present; nothing to patch
# ──────────────────────────────────────────────────────────────────────────────

import chromadb
from sentence_transformers import SentenceTransformer

from ..config import settings

logger = structlog.get_logger(__name__)
DEFAULT_MIN_SIMILARITY = 0.25


class VectorServiceError(Exception):
    """Custom exception for vector service errors."""


class VectorService:
    """Service for semantic vector search using ChromaDB."""

    def __init__(self):
        self._client = None
        self._collection = None
        self._embedding_model = None
        self._initialized = False
        self._index_lock = asyncio.Lock()

    @staticmethod
    def _collection_metadata(corpus_hash: Optional[str] = None) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {"description": "Singapore Tort Law Hypotheticals"}
        if corpus_hash:
            metadata["corpus_hash"] = corpus_hash
        return metadata

    def _initialize(self):
        """Initialize ChromaDB client and embedding model."""
        try:
            from ..config import settings as app_settings

            model_name = app_settings.embedding_model
            logger.info("Loading embedding model", model=model_name)
            self._embedding_model = SentenceTransformer(model_name)

            # Initialize ChromaDB client (local persistent storage)
            persist_directory = Path("./chroma_db")
            persist_directory.mkdir(parents=True, exist_ok=True)

            self._client = chromadb.PersistentClient(
                path=str(persist_directory),
                settings=chromadb.Settings(anonymized_telemetry=False),
            )

            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=settings.database.chroma_collection_name,
                metadata=self._collection_metadata(),
            )
            logger.info(
                "ChromaDB collection ready",
                name=settings.database.chroma_collection_name,
                count=self._collection.count(),
            )

            self._initialized = True
            logger.info("Vector service initialized successfully")

        except Exception as e:
            logger.error("Failed to initialize vector service", error=str(e))
            self._initialized = False
            raise VectorServiceError(
                f"Vector service initialization failed: {e}"
            ) from e

    def _embed_text(self, text: str) -> List[float]:
        """Generate embedding vector for text."""
        if not self._embedding_model:
            raise VectorServiceError("Embedding model not initialized")

        embedding = self._embedding_model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def _ensure_initialized(self):
        """Lazy init — only initialize on first use."""
        if not self._initialized:
            self._initialize()

    def get_indexed_corpus_hash(self) -> Optional[str]:
        """Return corpus hash currently attached to vector collection metadata."""
        self._ensure_initialized()
        if not self._initialized or self._collection is None:
            return None
        metadata = self._collection.metadata or {}
        corpus_hash = metadata.get("corpus_hash")
        if isinstance(corpus_hash, str) and corpus_hash.strip():
            return corpus_hash.strip()
        return None

    async def index_hypotheticals(
        self,
        hypotheticals: List[Dict[str, Any]],
        corpus_hash: Optional[str] = None,
    ) -> int:
        """
        Index hypotheticals in ChromaDB for semantic search.

        Args:
            hypotheticals: List of hypothetical entries with 'id', 'text', 'topics', 'metadata'
            corpus_hash: Optional hash of the source corpus for index freshness checks

        Returns:
            Number of entries indexed
        """
        self._ensure_initialized()
        if not self._initialized:
            raise VectorServiceError("Vector service not initialized")

        try:
            async with self._index_lock:
                # Clear existing collection
                if self._collection is not None and self._collection.count() > 0:
                    assert self._client is not None
                    self._client.delete_collection(settings.database.chroma_collection_name)
                    self._collection = self._client.create_collection(
                        name=settings.database.chroma_collection_name,
                        metadata=self._collection_metadata(corpus_hash),
                    )
                elif self._collection is not None and corpus_hash:
                    self._collection.modify(
                        metadata=self._collection_metadata(corpus_hash)
                    )

                # Prepare data for indexing
                ids = []
                documents = []
                metadatas = []
                embeddings = []

                for hypo in hypotheticals:
                    embedding = self._embed_text(hypo["text"])

                    ids.append(hypo["id"])
                    documents.append(hypo["text"])
                    embeddings.append(embedding)
                    metadatas.append(
                        {
                            "topics": ",".join(hypo.get("topics", [])),
                            "complexity": hypo.get("metadata", {}).get(
                                "complexity", "intermediate"
                            ),
                        }
                    )

                # Add to ChromaDB in batches
                batch_size = 100
                for i in range(0, len(ids), batch_size):
                    batch_end = min(i + batch_size, len(ids))
                    assert self._collection is not None
                    self._collection.add(
                        ids=ids[i:batch_end],
                        documents=documents[i:batch_end],
                        embeddings=embeddings[i:batch_end],
                        metadatas=metadatas[i:batch_end],
                    )

            logger.info(
                "Indexed hypotheticals",
                count=len(ids),
                corpus_hash=corpus_hash,
            )
            return len(ids)

        except Exception as e:
            logger.error("Failed to index hypotheticals", error=str(e))
            raise VectorServiceError(f"Indexing failed: {e}")

    async def semantic_search(
        self,
        query_topics: List[str],
        n_results: int = 5,
        exclude_ids: Optional[List[str]] = None,
        min_similarity: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search for relevant hypotheticals.

        Args:
            query_topics: List of topics to search for
            n_results: Number of results to return
            exclude_ids: IDs to exclude from results
            min_similarity: Minimum similarity threshold for relevance filtering

        Returns:
            List of relevant hypothetical entries with similarity scores
        """
        self._ensure_initialized()
        if not self._initialized:
            raise VectorServiceError("Vector service not available")

        try:
            similarity_threshold = (
                float(min_similarity)
                if min_similarity is not None
                else float(
                    getattr(
                        settings,
                        "vector_min_similarity",
                        DEFAULT_MIN_SIMILARITY,
                    )
                )
            )
            similarity_threshold = max(0.0, min(1.0, similarity_threshold))
            query_text = f"Legal hypothetical involving {', '.join(query_topics)} in Singapore tort law"

            query_embedding = self._embed_text(query_text)

            assert self._collection is not None
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(
                    n_results * 2,
                    self._collection.count(),
                ),
                include=["documents", "metadatas", "distances"],
            )

            candidates: List[Dict[str, Any]] = []
            exclude_set = set(exclude_ids) if exclude_ids else set()

            for i, doc_id in enumerate(results["ids"][0]):
                if doc_id in exclude_set:
                    continue

                distance = results["distances"][0][i]
                similarity_score = 1.0 / (1.0 + distance)

                candidates.append(
                    {
                        "id": doc_id,
                        "text": results["documents"][0][i],
                        "topics": results["metadatas"][0][i]["topics"].split(","),
                        "metadata": {
                            "complexity": results["metadatas"][0][i].get(
                                "complexity", "intermediate"
                            )
                        },
                        "similarity_score": similarity_score,
                    }
                )

            if not candidates:
                logger.info(
                    "Semantic search returned no candidate matches",
                    query_topics=query_topics,
                    threshold=similarity_threshold,
                )
                return []

            top_similarity = float(candidates[0]["similarity_score"])
            if top_similarity < similarity_threshold:
                logger.info(
                    "Semantic search below relevance threshold; using fallback retrieval",
                    query_topics=query_topics,
                    top_similarity=top_similarity,
                    threshold=similarity_threshold,
                )
                return []

            relevant_hypotheticals = [
                result
                for result in candidates
                if float(result["similarity_score"]) >= similarity_threshold
            ][:n_results]

            logger.info(
                "Semantic search completed",
                query_topics=query_topics,
                results_count=len(relevant_hypotheticals),
                threshold=similarity_threshold,
            )

            return relevant_hypotheticals

        except Exception as e:
            logger.error("Semantic search failed", error=str(e))
            raise VectorServiceError(f"Semantic search failed: {e}") from e

    async def health_check(self) -> Dict[str, Any]:
        """Check health of vector service."""
        health_status: Dict[str, Any] = {
            "initialized": self._initialized,
            "collection_count": 0,
            "embedding_model_loaded": (self._embedding_model is not None),
        }

        try:
            if self._initialized and self._collection:
                health_status["collection_count"] = self._collection.count()
        except Exception as e:
            logger.error("Vector service health check failed", error=str(e))
            health_status["error"] = str(e)

        return health_status


# Global vector service instance
vector_service = VectorService()
