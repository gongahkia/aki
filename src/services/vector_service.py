"""
Vector Service for semantic search using ChromaDB and sentence transformers.
Provides semantic similarity search for legal hypotheticals.
"""

import asyncio
import math
import re
import sys
import threading
from collections import Counter
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
LEGAL_BERT_MODEL = "nlpaueb/legal-bert-base-uncased"  # domain-specific alternative


class VectorServiceError(Exception):
    """Custom exception for vector service errors."""


class VectorService:
    """Service for semantic vector search using ChromaDB."""

    def __init__(self):
        self._client = None
        self._collection = None
        self._embedding_model = None
        self._initialized = False
        self._fallback_mode = False
        self._fallback_reason: Optional[str] = None
        self._index_lock = asyncio.Lock()
        self._init_lock = threading.Lock()
        self._reranker_model = None
        self._reranker_unavailable_reason: Optional[str] = None

    @staticmethod
    def _collection_metadata(corpus_hash: Optional[str] = None) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {"description": "Jikai legal hypotheticals"}
        if corpus_hash:
            metadata["corpus_hash"] = corpus_hash
        return metadata

    @staticmethod
    def _tokenize_legal_text(text: str) -> List[str]:
        tokens = re.findall(r"[a-zA-Z0-9]+(?:[-_][a-zA-Z0-9]+)?", text.lower())
        return [token.replace("_", " ") for token in tokens if len(token) > 1]

    @staticmethod
    def _bm25_rank_documents(
        query_text: str,
        documents: List[Dict[str, Any]],
        *,
        n_results: int,
    ) -> List[Dict[str, Any]]:
        query_tokens = VectorService._tokenize_legal_text(query_text)
        if not query_tokens or not documents:
            return []

        tokenized_docs: List[List[str]] = []
        for document in documents:
            topics = " ".join(str(topic) for topic in document.get("topics", []))
            tokenized_docs.append(
                VectorService._tokenize_legal_text(
                    f"{topics} {document.get('text', '')}"
                )
            )

        doc_count = len(tokenized_docs)
        avg_doc_len = (
            sum(len(tokens) for tokens in tokenized_docs) / max(doc_count, 1)
        ) or 1.0
        document_frequencies: Counter[str] = Counter()
        for tokens in tokenized_docs:
            document_frequencies.update(set(tokens))

        k1 = 1.5
        b = 0.75
        ranked: List[Dict[str, Any]] = []
        for document, tokens in zip(documents, tokenized_docs):
            term_counts = Counter(tokens)
            doc_len = len(tokens) or 1
            score = 0.0
            for token in query_tokens:
                tf = term_counts.get(token, 0)
                if tf == 0:
                    continue
                df = document_frequencies.get(token, 0)
                idf = math.log(1 + ((doc_count - df + 0.5) / (df + 0.5)))
                denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
                score += idf * ((tf * (k1 + 1)) / denominator)
            if score > 0:
                ranked.append({**document, "bm25_score": score})

        ranked.sort(key=lambda item: float(item["bm25_score"]), reverse=True)
        return ranked[:n_results]

    @staticmethod
    def _reciprocal_rank_fusion(
        rankings: List[List[str]], *, k: int = 60
    ) -> Dict[str, float]:
        scores: Dict[str, float] = {}
        for ranking in rankings:
            for rank, document_id in enumerate(ranking, start=1):
                scores[document_id] = scores.get(document_id, 0.0) + (1 / (k + rank))
        return scores

    def _get_cross_encoder_reranker(self):
        model_name = str(
            getattr(settings, "retrieval_reranker_model", "") or ""
        ).strip()
        if not model_name:
            return None
        if self._reranker_model is not None:
            return self._reranker_model
        try:
            from sentence_transformers import CrossEncoder

            self._reranker_model = CrossEncoder(model_name)
            self._reranker_unavailable_reason = None
            return self._reranker_model
        except Exception as exc:
            self._reranker_unavailable_reason = str(exc)
            logger.warning(
                "Cross-encoder reranker unavailable; using fused order",
                model=model_name,
                error=str(exc),
            )
            return None

    def _rerank_with_cross_encoder(
        self, query_text: str, results: List[Dict[str, Any]], *, n_results: int
    ) -> List[Dict[str, Any]]:
        reranker = self._get_cross_encoder_reranker()
        if reranker is None or not results:
            return results[:n_results]
        try:
            pairs = [(query_text, str(result.get("text", ""))) for result in results]
            scores = reranker.predict(pairs)
            reranked = []
            for result, score in zip(results, scores):
                reranked.append({**result, "reranker_score": float(score)})
            reranked.sort(
                key=lambda item: float(item.get("reranker_score", 0.0)),
                reverse=True,
            )
            return reranked[:n_results]
        except Exception as exc:
            logger.warning("Cross-encoder rerank failed", error=str(exc))
            return results[:n_results]

    def _initialize(self):
        """Initialize ChromaDB client and embedding model."""
        try:
            from ..config import settings as app_settings

            model_name = app_settings.embedding_model
            use_legal_bert = getattr(app_settings, "use_legal_bert_embeddings", False)
            if use_legal_bert:
                model_name = LEGAL_BERT_MODEL
                logger.info("Using Legal-BERT for domain-specific embeddings")
            logger.info("Loading embedding model", model=model_name)
            try:
                self._embedding_model = SentenceTransformer(model_name)
            except Exception as embed_error:
                self._embedding_model = None
                self._fallback_mode = True
                self._fallback_reason = f"embedding model load failed: {embed_error}"
                self._initialized = True
                logger.warning(
                    "Embedding model unavailable; vector service running in fallback mode",
                    model=model_name,
                    error=str(embed_error),
                )
                return

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

            self._fallback_mode = False
            self._fallback_reason = None
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
            with self._init_lock:
                if not self._initialized:
                    self._initialize()

    def get_indexed_corpus_hash(self) -> Optional[str]:
        """Return corpus hash currently attached to vector collection metadata."""
        self._ensure_initialized()
        if self._fallback_mode:
            return None
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
        if self._fallback_mode:
            logger.warning(
                "Vector indexing skipped; running in fallback mode",
                reason=self._fallback_reason,
            )
            return 0
        if not self._initialized:
            raise VectorServiceError("Vector service not initialized")

        try:
            async with self._index_lock:
                # Clear existing collection
                if self._collection is not None and self._collection.count() > 0:
                    assert self._client is not None
                    self._client.delete_collection(
                        settings.database.chroma_collection_name
                    )
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
                            "corpus_pack_key": hypo.get("corpus_pack_key", "sg_tort"),
                            "jurisdiction": hypo.get("jurisdiction", "sg"),
                            "subject": hypo.get("subject", "tort"),
                            "subtopics": ",".join(hypo.get("subtopics", [])),
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

    async def hybrid_search(
        self,
        query_topics: List[str],
        corpus_documents: List[Dict[str, Any]],
        corpus_pack: str = "sg_tort",
        jurisdiction: str = "sg",
        subject: str = "tort",
        subtopics: Optional[List[str]] = None,
        n_results: int = 5,
        exclude_ids: Optional[List[str]] = None,
        min_similarity: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        query_text = (
            f"Legal hypothetical involving {', '.join(query_topics)} "
            f"in {jurisdiction} {subject} law"
        )
        pool_size = max(n_results * 4, 10)
        exclude_set = {str(document_id) for document_id in (exclude_ids or [])}
        filtered_documents = [
            document
            for document in corpus_documents
            if str(document.get("id")) not in exclude_set
        ]
        lexical_results = self._bm25_rank_documents(
            query_text,
            filtered_documents,
            n_results=pool_size,
        )

        dense_results: List[Dict[str, Any]] = []
        try:
            dense_results = await self.semantic_search(
                query_topics=query_topics,
                corpus_pack=corpus_pack,
                jurisdiction=jurisdiction,
                subject=subject,
                subtopics=subtopics,
                n_results=pool_size,
                exclude_ids=exclude_ids,
                min_similarity=min_similarity,
            )
        except Exception as exc:
            logger.info(
                "Dense branch unavailable during hybrid search",
                error=str(exc),
            )

        rankings = []
        if dense_results:
            rankings.append([str(result["id"]) for result in dense_results])
        if lexical_results:
            rankings.append([str(result["id"]) for result in lexical_results])
        if not rankings:
            return []

        rrf_k = int(getattr(settings, "retrieval_rrf_k", 60))
        fused_scores = self._reciprocal_rank_fusion(rankings, k=rrf_k)
        by_id: Dict[str, Dict[str, Any]] = {}
        for result in dense_results:
            by_id[str(result["id"])] = {
                **result,
                "dense_score": result.get("similarity_score"),
            }
        for result in lexical_results:
            document_id = str(result["id"])
            by_id[document_id] = {
                **by_id.get(document_id, result),
                **result,
                "lexical_score": result.get("bm25_score"),
            }

        dense_ids = {str(item["id"]) for item in dense_results}
        lexical_ids = {str(item["id"]) for item in lexical_results}
        fused_results = []
        for document_id, score in fused_scores.items():
            fused_result = by_id.get(document_id)
            if not fused_result:
                continue
            fused_results.append(
                {
                    **fused_result,
                    "rrf_score": score,
                    "retrieval_mode": "hybrid",
                    "retrieval_branches": {
                        "dense": document_id in dense_ids,
                        "lexical": document_id in lexical_ids,
                    },
                }
            )

        fused_results.sort(
            key=lambda item: float(item.get("rrf_score", 0.0)),
            reverse=True,
        )
        reranked = self._rerank_with_cross_encoder(
            query_text,
            fused_results,
            n_results=n_results,
        )
        logger.info(
            "Hybrid search completed",
            query_topics=query_topics,
            dense_count=len(dense_results),
            lexical_count=len(lexical_results),
            results_count=len(reranked),
            rrf_k=rrf_k,
        )
        return reranked

    async def semantic_search(
        self,
        query_topics: List[str],
        corpus_pack: str = "sg_tort",
        jurisdiction: str = "sg",
        subject: str = "tort",
        subtopics: Optional[List[str]] = None,
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
        if self._fallback_mode:
            logger.info(
                "Vector search unavailable; returning no semantic matches",
                reason=self._fallback_reason,
            )
            return []
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
            query_text = (
                f"Legal hypothetical involving {', '.join(query_topics)} "
                f"in {jurisdiction} {subject} law"
            )

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
            subtopic_set = set(subtopics or [])

            for i, doc_id in enumerate(results["ids"][0]):
                if doc_id in exclude_set:
                    continue
                metadata = results["metadatas"][0][i] or {}
                metadata_subtopics = [
                    value
                    for value in str(metadata.get("subtopics", "")).split(",")
                    if value
                ]
                metadata_pack = metadata.get("corpus_pack_key", "sg_tort")
                metadata_jurisdiction = metadata.get("jurisdiction", "sg")
                metadata_subject = metadata.get("subject", "tort")
                if corpus_pack and metadata_pack != corpus_pack:
                    continue
                if jurisdiction and metadata_jurisdiction != jurisdiction:
                    continue
                if subject and metadata_subject != subject:
                    continue
                if subtopic_set and not (subtopic_set & set(metadata_subtopics)):
                    continue

                distance = results["distances"][0][i]
                similarity_score = 1.0 / (1.0 + distance)

                candidates.append(
                    {
                        "id": doc_id,
                        "text": results["documents"][0][i],
                        "topics": metadata["topics"].split(","),
                        "corpus_pack_key": metadata_pack,
                        "jurisdiction": metadata_jurisdiction,
                        "subject": metadata_subject,
                        "subtopics": metadata_subtopics,
                        "metadata": {
                            "complexity": metadata.get("complexity", "intermediate")
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
            "fallback_mode": self._fallback_mode,
            "fallback_reason": self._fallback_reason,
            "retrieval_mode": getattr(settings, "retrieval_mode", "dense"),
            "reranker_configured": bool(
                getattr(settings, "retrieval_reranker_model", None)
            ),
            "reranker_loaded": self._reranker_model is not None,
            "reranker_unavailable_reason": self._reranker_unavailable_reason,
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
