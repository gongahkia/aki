"""
Vector Service for semantic search using ChromaDB and sentence transformers.
Provides semantic similarity search for legal hypotheticals.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
import structlog
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from ..config import settings

logger = structlog.get_logger(__name__)


class VectorServiceError(Exception):
    """Custom exception for vector service errors."""


class VectorService:
    """Service for semantic vector search using ChromaDB."""

    def __init__(self):
        self._client: Optional[chromadb.ClientAPI] = None
        self._collection: Optional[chromadb.Collection] = None
        self._embedding_model: Optional[SentenceTransformer] = None
        self._initialized = False
        self._initialize()

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

            self._client = chromadb.Client(
                ChromaSettings(
                    persist_directory=str(persist_directory), anonymized_telemetry=False
                )
            )

            # Get or create collection
            try:
                self._collection = self._client.get_collection(
                    name=settings.database.chroma_collection_name
                )
                logger.info(
                    "Loaded existing ChromaDB collection",
                    name=settings.database.chroma_collection_name,
                    count=self._collection.count(),
                )
            except Exception:
                self._collection = self._client.create_collection(
                    name=settings.database.chroma_collection_name,
                    metadata={"description": "Singapore Tort Law Hypotheticals"},
                )
                logger.info(
                    "Created new ChromaDB collection",
                    name=settings.database.chroma_collection_name,
                )

            self._initialized = True
            logger.info("Vector service initialized successfully")

        except (ImportError, OSError, RuntimeError) as e:
            logger.error("Failed to initialize vector service", error=str(e))
            self._initialized = False
            # Don't raise - allow fallback to simple search

    def _embed_text(self, text: str) -> List[float]:
        """Generate embedding vector for text."""
        if not self._embedding_model:
            raise VectorServiceError("Embedding model not initialized")

        # Generate embedding
        embedding = self._embedding_model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    async def index_hypotheticals(self, hypotheticals: List[Dict[str, Any]]) -> int:
        """
        Index hypotheticals in ChromaDB for semantic search.

        Args:
            hypotheticals: List of hypothetical entries with 'id', 'text', 'topics', 'metadata'

        Returns:
            Number of entries indexed
        """
        if not self._initialized:
            raise VectorServiceError("Vector service not initialized")

        try:
            # Clear existing collection
            if self._collection is not None and self._collection.count() > 0:
                assert self._client is not None
                self._client.delete_collection(settings.database.chroma_collection_name)
                self._collection = self._client.create_collection(
                    name=settings.database.chroma_collection_name,
                    metadata={"description": "Singapore Tort Law Hypotheticals"},
                )

            # Prepare data for indexing
            ids = []
            documents = []
            metadatas = []
            embeddings = []

            for hypo in hypotheticals:
                # Generate embedding for the hypothetical text
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

            logger.info("Indexed hypotheticals", count=len(ids))
            return len(ids)

        except Exception as e:
            logger.error("Failed to index hypotheticals", error=str(e))
            raise VectorServiceError(f"Indexing failed: {e}")

    async def semantic_search(
        self,
        query_topics: List[str],
        n_results: int = 5,
        exclude_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Perform semantic search for relevant hypotheticals.

        Args:
            query_topics: List of topics to search for
            n_results: Number of results to return
            exclude_ids: IDs to exclude from results

        Returns:
            List of relevant hypothetical entries with similarity scores
        """
        if not self._initialized:
            logger.warning("Vector service not initialized, returning empty results")
            return []

        try:
            # Create query text from topics
            query_text = f"Legal hypothetical involving {', '.join(query_topics)} in Singapore tort law"

            # Generate query embedding
            query_embedding = self._embed_text(query_text)

            # Perform semantic search
            assert self._collection is not None
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=min(
                    n_results * 2,
                    self._collection.count(),
                ),  # Get extra for filtering
                include=["documents", "metadatas", "distances"],
            )

            # Process and filter results
            relevant_hypotheticals: List[Dict[str, Any]] = []
            exclude_set = set(exclude_ids) if exclude_ids else set()

            for i, doc_id in enumerate(results["ids"][0]):
                if doc_id in exclude_set:
                    continue

                if len(relevant_hypotheticals) >= n_results:
                    break

                # Convert distance to similarity score (smaller distance = more similar)
                distance = results["distances"][0][i]
                similarity_score = 1.0 / (1.0 + distance)  # Convert to 0-1 range

                relevant_hypotheticals.append(
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

            logger.info(
                "Semantic search completed",
                query_topics=query_topics,
                results_count=len(relevant_hypotheticals),
            )

            return relevant_hypotheticals

        except Exception as e:
            logger.error("Semantic search failed", error=str(e))
            return []  # Return empty list instead of raising

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
