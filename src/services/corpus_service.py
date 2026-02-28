"""
Corpus Service for managing legal hypothetical corpus data.
Handles both local file storage and AWS S3 integration.
"""

import json
import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import structlog
from botocore.exceptions import ClientError
from pydantic import BaseModel, Field

from ..config import settings
from .vector_service import VectorServiceError, vector_service

logger = structlog.get_logger(__name__)


class HypotheticalEntry(BaseModel):
    """Model for a single hypothetical entry."""

    id: Optional[str] = None
    text: str
    topics: List[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CorpusQuery(BaseModel):
    """Model for corpus queries."""

    topics: List[str]
    sample_size: int = Field(default=5, ge=1, le=50)
    exclude_ids: List[str] = Field(default_factory=list)
    min_topic_overlap: int = Field(default=1, ge=1)


class CorpusServiceError(Exception):
    """Custom exception for corpus service errors."""


class CorpusService:
    """Service for managing legal hypothetical corpus data."""

    def __init__(self):
        from ..config import settings as app_settings

        self._local_corpus_path = Path(app_settings.corpus_path)
        self._s3_client = None
        self._vector_service = vector_service
        self._corpus_indexed = False
        self._index_lock = asyncio.Lock()
        self._topics_cache: Optional[List[str]] = None
        self._topics_cache_mtime: Optional[float] = None
        self._initialize_s3()

    def _get_local_corpus_mtime(self) -> Optional[float]:
        try:
            return self._local_corpus_path.stat().st_mtime
        except OSError:
            return None

    def _invalidate_topic_cache(self):
        self._topics_cache = None
        self._topics_cache_mtime = None

    def _initialize_s3(self):
        """Initialize AWS S3 client if credentials are available."""
        try:
            if settings.aws.access_key_id and settings.aws.secret_access_key:
                self._s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=settings.aws.access_key_id,
                    aws_secret_access_key=settings.aws.secret_access_key,
                    region_name=settings.aws.region,
                )
                logger.info("S3 client initialized", bucket=settings.aws.s3_bucket)
            else:
                logger.warning("S3 credentials not provided, using local storage only")
        except Exception as e:
            logger.error("Failed to initialize S3 client", error=str(e))
            self._s3_client = None

    async def load_corpus(self, source: str = "local") -> List[HypotheticalEntry]:
        """Load corpus from local file or S3."""
        try:
            if source == "s3" and self._s3_client:
                return await self._load_from_s3()
            else:
                return await self._load_from_local()
        except Exception as e:
            logger.error("Failed to load corpus", source=source, error=str(e))
            raise CorpusServiceError(f"Failed to load corpus: {e}")

    async def _load_from_local(self) -> List[HypotheticalEntry]:
        """Load corpus from local JSON file."""
        if not self._local_corpus_path.exists():
            raise CorpusServiceError(
                f"Local corpus file not found: {self._local_corpus_path}"
            )

        try:
            with open(self._local_corpus_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            entries = []
            for i, item in enumerate(data):
                entry = HypotheticalEntry(
                    id=str(i),
                    text=item.get("text", ""),
                    topics=item.get("topic", []),
                    metadata=item.get("metadata", {}),
                    created_at=item.get("created_at"),
                    updated_at=item.get("updated_at"),
                )
                entries.append(entry)

            logger.info("Corpus loaded from local file", entries_count=len(entries))
            return entries

        except json.JSONDecodeError as e:
            raise CorpusServiceError(f"Invalid JSON in corpus file: {e}")
        except Exception as e:
            raise CorpusServiceError(f"Error reading local corpus: {e}")

    async def _load_from_s3(self) -> List[HypotheticalEntry]:
        """Load corpus from S3 bucket."""
        try:
            assert self._s3_client is not None
            response = self._s3_client.get_object(
                Bucket=settings.aws.s3_bucket, Key="corpus/tort/corpus.json"
            )

            data = json.loads(response["Body"].read().decode("utf-8"))

            entries = []
            for i, item in enumerate(data):
                entry = HypotheticalEntry(
                    id=str(i),
                    text=item.get("text", ""),
                    topics=item.get("topic", []),
                    metadata=item.get("metadata", {}),
                    created_at=item.get("created_at"),
                    updated_at=item.get("updated_at"),
                )
                entries.append(entry)

            logger.info("Corpus loaded from S3", entries_count=len(entries))
            return entries

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "NoSuchKey":
                raise CorpusServiceError("Corpus file not found in S3 bucket")
            else:
                raise CorpusServiceError(f"S3 error: {e}")
        except Exception as e:
            raise CorpusServiceError(f"Error loading from S3: {e}")

    async def save_corpus(
        self, entries: List[HypotheticalEntry], destination: str = "local"
    ) -> bool:
        """Save corpus to local file or S3."""
        try:
            if destination == "s3" and self._s3_client:
                return await self._save_to_s3(entries)
            else:
                return await self._save_to_local(entries)
        except Exception as e:
            logger.error("Failed to save corpus", destination=destination, error=str(e))
            raise CorpusServiceError(f"Failed to save corpus: {e}")

    async def _save_to_local(self, entries: List[HypotheticalEntry]) -> bool:
        """Save corpus to local JSON file."""
        try:
            # Ensure directory exists
            self._local_corpus_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert to JSON-serializable format
            data = []
            for entry in entries:
                data.append(
                    {
                        "text": entry.text,
                        "topic": entry.topics,
                        "metadata": entry.metadata,
                        "created_at": entry.created_at,
                        "updated_at": entry.updated_at,
                    }
                )

            with open(self._local_corpus_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            self._invalidate_topic_cache()
            logger.info("Corpus saved to local file", entries_count=len(entries))
            return True

        except Exception as e:
            raise CorpusServiceError(f"Error saving to local file: {e}")

    async def _save_to_s3(self, entries: List[HypotheticalEntry]) -> bool:
        """Save corpus to S3 bucket."""
        try:
            # Convert to JSON-serializable format
            data = []
            for entry in entries:
                data.append(
                    {
                        "text": entry.text,
                        "topic": entry.topics,
                        "metadata": entry.metadata,
                        "created_at": entry.created_at,
                        "updated_at": entry.updated_at,
                    }
                )

            json_data = json.dumps(data, indent=2, ensure_ascii=False)

            assert self._s3_client is not None
            self._s3_client.put_object(
                Bucket=settings.aws.s3_bucket,
                Key="corpus/tort/corpus.json",
                Body=json_data.encode("utf-8"),
                ContentType="application/json",
            )

            self._invalidate_topic_cache()
            logger.info("Corpus saved to S3", entries_count=len(entries))
            return True

        except ClientError as e:
            raise CorpusServiceError(f"S3 error: {e}")
        except Exception as e:
            raise CorpusServiceError(f"Error saving to S3: {e}")

    async def query_relevant_hypotheticals(
        self, query: CorpusQuery
    ) -> List[HypotheticalEntry]:
        """
        Query corpus for relevant hypotheticals using semantic search.
        Falls back to simple topic matching if vector search unavailable.
        """
        try:
            # Ensure corpus is indexed in vector DB
            await self._ensure_corpus_indexed()

            # Try semantic search first (ChromaDB + embeddings)
            try:
                results = await self._vector_service.semantic_search(
                    query_topics=query.topics,
                    n_results=query.sample_size,
                    exclude_ids=query.exclude_ids,
                )

                if results:
                    # Convert vector search results back to HypotheticalEntry
                    relevant_entries = []
                    for result in results:
                        entry = HypotheticalEntry(
                            id=result["id"],
                            text=result["text"],
                            topics=result["topics"],
                            metadata=result["metadata"],
                        )
                        relevant_entries.append(entry)

                    logger.info(
                        "Semantic search completed",
                        query_topics=query.topics,
                        results_count=len(relevant_entries),
                    )
                    return relevant_entries

            except (VectorServiceError, Exception) as ve:
                logger.warning(
                    "Vector search failed, falling back to simple search", error=str(ve)
                )

            # Fallback: Simple topic overlap (original method)
            corpus = await self.load_corpus()
            available_entries = [
                entry for entry in corpus if entry.id not in query.exclude_ids
            ]

            scored_entries = []
            for entry in available_entries:
                overlap_count = len(set(entry.topics) & set(query.topics))
                if overlap_count >= query.min_topic_overlap:
                    scored_entries.append((entry, overlap_count))

            scored_entries.sort(key=lambda x: x[1], reverse=True)
            relevant_entries = [
                entry for entry, _ in scored_entries[: query.sample_size]
            ]

            logger.info(
                "Fallback search completed",
                query_topics=query.topics,
                results_count=len(relevant_entries),
                method="topic_overlap",
            )

            return relevant_entries

        except Exception as e:
            logger.error("Corpus query failed", error=str(e))
            raise CorpusServiceError(f"Corpus query failed: {e}")

    async def _index_corpus(self):
        """Index corpus in vector database for semantic search."""
        try:
            corpus = await self.load_corpus()

            # Convert to format expected by vector service
            hypotheticals_data = []
            for entry in corpus:
                hypotheticals_data.append(
                    {
                        "id": entry.id,
                        "text": entry.text,
                        "topics": entry.topics,
                        "metadata": entry.metadata,
                    }
                )

            # Index in vector database
            count = await self._vector_service.index_hypotheticals(hypotheticals_data)
            self._corpus_indexed = True

            logger.info("Corpus indexed in vector database", count=count)

        except Exception as e:
            logger.warning("Failed to index corpus in vector database", error=str(e))
            self._corpus_indexed = False
            # Don't raise - allow fallback to simple search

    async def _ensure_corpus_indexed(self):
        """Protect first-time index bootstrap under concurrent access."""
        if self._corpus_indexed:
            return
        async with self._index_lock:
            if self._corpus_indexed:
                return
            await self._index_corpus()

    async def extract_all_topics(self) -> List[str]:
        """Extract all unique topics from the corpus."""
        try:
            current_mtime = self._get_local_corpus_mtime()
            if (
                self._topics_cache is not None
                and current_mtime is not None
                and self._topics_cache_mtime == current_mtime
            ):
                return list(self._topics_cache)

            corpus = await self.load_corpus()
            all_topics = set()

            for entry in corpus:
                all_topics.update(entry.topics)

            topics_list = sorted(list(all_topics))
            if current_mtime is not None:
                self._topics_cache = topics_list
                self._topics_cache_mtime = current_mtime
            else:
                self._invalidate_topic_cache()
            logger.info("Topics extracted", topics_count=len(topics_list))

            return topics_list

        except Exception as e:
            logger.error("Topic extraction failed", error=str(e))
            raise CorpusServiceError(f"Topic extraction failed: {e}")

    async def add_hypothetical(
        self, entry: HypotheticalEntry, destination: str = "local"
    ) -> str:
        """Add a new hypothetical to the corpus."""
        try:
            corpus = await self.load_corpus()

            # Generate ID if not provided
            if not entry.id:
                entry.id = str(len(corpus))

            # Add timestamps
            from datetime import datetime

            now = datetime.utcnow().isoformat()
            entry.created_at = now
            entry.updated_at = now

            corpus.append(entry)

            # Save updated corpus
            await self.save_corpus(corpus, destination)

            logger.info(
                "Hypothetical added to corpus", id=entry.id, topics=entry.topics
            )
            return entry.id

        except Exception as e:
            logger.error("Failed to add hypothetical", error=str(e))
            raise CorpusServiceError(f"Failed to add hypothetical: {e}")

    async def update_hypothetical(
        self, entry_id: str, updates: Dict[str, Any], destination: str = "local"
    ) -> bool:
        """Update an existing hypothetical in the corpus."""
        try:
            corpus = await self.load_corpus()

            # Find the entry
            entry_index = None
            for i, entry in enumerate(corpus):
                if entry.id == entry_id:
                    entry_index = i
                    break

            if entry_index is None:
                raise CorpusServiceError(f"Hypothetical with ID {entry_id} not found")

            # Update the entry
            entry = corpus[entry_index]
            for key, value in updates.items():
                if hasattr(entry, key):
                    setattr(entry, key, value)

            # Update timestamp
            from datetime import datetime

            entry.updated_at = datetime.utcnow().isoformat()

            # Save updated corpus
            await self.save_corpus(corpus, destination)

            logger.info(
                "Hypothetical updated", id=entry_id, updates=list(updates.keys())
            )
            return True

        except Exception as e:
            logger.error("Failed to update hypothetical", id=entry_id, error=str(e))
            raise CorpusServiceError(f"Failed to update hypothetical: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Check the health of the corpus service."""
        health_status = {
            "local_corpus": False,
            "s3_available": False,
            "total_entries": 0,
            "topics_count": 0,
        }

        try:
            # Check local corpus
            if self._local_corpus_path.exists():
                corpus = await self.load_corpus("local")
                health_status["local_corpus"] = True
                health_status["total_entries"] = len(corpus)
                health_status["topics_count"] = len(await self.extract_all_topics())

            # Check S3 availability
            if self._s3_client:
                try:
                    self._s3_client.head_bucket(Bucket=settings.aws.s3_bucket)
                    health_status["s3_available"] = True
                except ClientError:
                    health_status["s3_available"] = False

        except Exception as e:
            logger.error("Health check failed", error=str(e))

        return health_status


# Global corpus service instance
corpus_service = CorpusService()
