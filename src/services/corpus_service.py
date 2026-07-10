import asyncio
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel, Field, field_validator

from src.corpus_ingestion import read_ingestion_health

from ..config import settings
from ..domain import canonicalize_topic, normalize_scope_token, resolve_domain_pack
from .vector_service import VectorServiceError, vector_service

logger = structlog.get_logger(__name__)


class HypotheticalEntry(BaseModel):
    """Model for a single hypothetical entry."""

    id: Optional[str] = None
    text: str
    topics: List[str]
    question_prompt: Optional[str] = None
    fact_pattern: Optional[str] = None
    issues_expected: List[str] = Field(default_factory=list)
    model_answer: Optional[str] = None
    marking_rubric: Any = None
    difficulty: Optional[str] = None
    time_limit_minutes: Optional[int] = None
    jurisdiction_notes: Optional[str] = None
    answer_visibility: str = "hidden"
    source_exam_context: Dict[str, Any] = Field(default_factory=dict)
    corpus_pack_key: str = "sg_tort"
    jurisdiction: str = "sg"
    subject: str = "tort"
    subtopics: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @field_validator("answer_visibility")
    @classmethod
    def validate_answer_visibility(cls, value: str) -> str:
        allowed = {"hidden", "visible", "after_attempt"}
        normalized = str(value or "hidden").strip().lower()
        if normalized not in allowed:
            raise ValueError(f"answer_visibility must be one of {sorted(allowed)}")
        return normalized

    @property
    def practice_fact_pattern(self) -> str:
        return self.fact_pattern or self.text

    def student_view(self, *, include_model_answer: bool = False) -> Dict[str, Any]:
        payload = self.model_dump(mode="json", exclude_none=True)
        payload["fact_pattern"] = self.practice_fact_pattern
        if not include_model_answer:
            payload.pop("model_answer", None)
            payload.pop("marking_rubric", None)
        return payload


class CorpusQuery(BaseModel):
    """Model for corpus queries."""

    topics: List[str]
    corpus_pack: str = "sg_tort"
    jurisdiction: str = "sg"
    subject: str = "tort"
    subtopics: List[str] = Field(default_factory=list)
    sample_size: int = Field(default=5, ge=1, le=50)
    exclude_ids: List[str] = Field(default_factory=list)
    min_topic_overlap: int = Field(default=1, ge=1)

    @field_validator("corpus_pack", "jurisdiction", "subject")
    @classmethod
    def normalize_scope_fields(cls, value: str) -> str:
        return CorpusService._normalize_scope(value, "sg")

    @field_validator("subtopics")
    @classmethod
    def normalize_subtopics(cls, value: List[str]) -> List[str]:
        return CorpusService._normalize_string_list(value)


class CorpusServiceError(Exception):
    """Custom exception for corpus service errors."""


class CorpusService:
    """Service for managing legal hypothetical corpus data."""

    def __init__(self):
        from ..config import settings as app_settings

        self._local_corpus_path = Path(app_settings.corpus_path)
        self._vector_service = vector_service
        self._corpus_indexed = False
        self._index_lock = asyncio.Lock()
        self._index_task: Optional[asyncio.Task] = None
        self._index_task_lock = asyncio.Lock()
        self._topics_cache: Optional[List[str]] = None
        self._topics_cache_mtime: Optional[float] = None
        self._topics_cache_lock = asyncio.Lock()
        self._indexed_corpus_hash: Optional[str] = None

    def _resolve_corpus_path(self, corpus_pack: str = "sg_tort") -> Path:
        try:
            domain_pack = resolve_domain_pack(corpus_pack)
        except KeyError:
            return self._local_corpus_path
        if domain_pack.corpus_path:
            return Path(domain_pack.corpus_path)
        return self._local_corpus_path

    def _resolve_corpus_paths(self, corpus_pack: str = "sg_tort") -> List[Path]:
        primary_path = self._resolve_corpus_path(corpus_pack)
        try:
            domain_pack = resolve_domain_pack(corpus_pack)
        except KeyError:
            return [primary_path]
        paths = [primary_path]
        for path_text in domain_pack.supplemental_corpus_paths:
            path = Path(path_text)
            if path not in paths:
                paths.append(path)
        return paths

    def _get_local_corpus_mtime(self, corpus_pack: str = "sg_tort") -> Optional[float]:
        mtimes = []
        for corpus_path in self._resolve_corpus_paths(corpus_pack):
            try:
                mtimes.append(corpus_path.stat().st_mtime)
            except OSError:
                continue
        if mtimes:
            return max(mtimes)
        return None

    async def _invalidate_topic_cache(self):
        async with self._topics_cache_lock:
            self._topics_cache = None
            self._topics_cache_mtime = None

    def _compute_current_corpus_hash(
        self, corpus_pack: str = "sg_tort"
    ) -> Optional[str]:
        digest = hashlib.sha256()
        saw_file = False
        for corpus_path in self._resolve_corpus_paths(corpus_pack):
            try:
                payload = corpus_path.read_bytes()
            except OSError:
                continue
            saw_file = True
            digest.update(str(corpus_path).encode("utf-8"))
            digest.update(b"\0")
            digest.update(payload)
            digest.update(b"\0")
        if saw_file:
            return digest.hexdigest()
        return None

    @staticmethod
    def _compute_entries_hash(entries: List[HypotheticalEntry]) -> str:
        normalized_entries = [
            {
                "id": entry.id,
                "text": entry.text,
                "topics": list(entry.topics),
                "metadata": entry.metadata,
            }
            for entry in entries
        ]
        serialized = json.dumps(normalized_entries, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_topics(raw_topics: Any) -> List[str]:
        if raw_topics is None:
            return []
        if isinstance(raw_topics, list):
            values = raw_topics
        else:
            values = [raw_topics]
        normalized: List[str] = []
        for topic in values:
            text = str(topic).strip()
            if not text:
                continue
            canonical = canonicalize_topic(text)
            if canonical not in normalized:
                normalized.append(canonical)
        return normalized

    @staticmethod
    def _normalize_scope(value: Any, fallback: str) -> str:
        text = str(value or "").strip()
        if not text:
            return fallback
        token = normalize_scope_token(text)
        if token in {"singapore", "singapore_law", "singapore_tort"}:
            return "sg"
        if token in {
            "united_states",
            "united_states_of_america",
            "usa",
            "u.s.",
            "u.s.a.",
        }:
            return "us"
        if token in {
            "united_kingdom",
            "great_britain",
            "england_and_wales",
            "england",
            "wales",
        }:
            return "uk"
        return token

    @staticmethod
    def _normalize_string_list(raw_values: Any) -> List[str]:
        if raw_values is None:
            return []
        if isinstance(raw_values, list):
            values = raw_values
        else:
            values = [raw_values]
        normalized: List[str] = []
        for value in values:
            token = normalize_scope_token(str(value))
            if token and token not in normalized:
                normalized.append(token)
        return normalized

    @staticmethod
    def _preserve_string_list(raw_values: Any) -> List[str]:
        if raw_values is None:
            return []
        if isinstance(raw_values, list):
            values = raw_values
        else:
            values = [raw_values]
        return [str(value).strip() for value in values if str(value).strip()]

    @staticmethod
    def _entry_value(
        item: Dict[str, Any], metadata: Dict[str, Any], key: str, default: Any = None
    ) -> Any:
        if key in item:
            return item[key]
        if key in metadata:
            return metadata[key]
        return default

    @classmethod
    def _entry_scope_from_item(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        default_pack = resolve_domain_pack("sg_tort")
        metadata = item.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        corpus_pack_key = (
            item.get("corpus_pack_key")
            or item.get("corpus_pack")
            or metadata.get("corpus_pack_key")
            or metadata.get("corpus_pack")
            or default_pack.key
        )
        subject = (
            item.get("subject")
            or item.get("law_domain")
            or metadata.get("subject")
            or metadata.get("law_domain")
            or default_pack.subject_key
        )
        jurisdiction = (
            item.get("jurisdiction")
            or metadata.get("jurisdiction")
            or default_pack.jurisdiction_key
        )
        subtopics = item.get("subtopics", metadata.get("subtopics", []))
        return {
            "corpus_pack_key": cls._normalize_scope(corpus_pack_key, default_pack.key),
            "jurisdiction": cls._normalize_scope(
                jurisdiction, default_pack.jurisdiction_key
            ),
            "subject": cls._normalize_scope(subject, default_pack.subject_key),
            "subtopics": cls._normalize_string_list(subtopics),
        }

    @staticmethod
    def _entry_matches_scope(entry: HypotheticalEntry, query: CorpusQuery) -> bool:
        if query.corpus_pack and entry.corpus_pack_key != query.corpus_pack:
            return False
        if query.jurisdiction and entry.jurisdiction != query.jurisdiction:
            return False
        if query.subject and entry.subject != query.subject:
            return False
        if query.subtopics and not (set(entry.subtopics) & set(query.subtopics)):
            return False
        return True

    @staticmethod
    def _entry_is_default_retrievable(entry: HypotheticalEntry) -> bool:
        metadata = entry.metadata if isinstance(entry.metadata, dict) else {}
        context = (
            entry.source_exam_context
            if isinstance(entry.source_exam_context, dict)
            else {}
        )
        synthetic_marker = (
            metadata.get("synthetic_status")
            or context.get("synthetic_status")
            or metadata.get("generator")
        )
        if not synthetic_marker:
            return True
        context_reviewed = context.get("generated_reviewed")
        return (
            metadata.get("synthetic_status") == "generated_reviewed"
            and metadata.get("generated_reviewed") is True
            and metadata.get("review_status") == "reviewed"
            and (context_reviewed is True or "generated_reviewed" not in context)
        )

    async def load_corpus(
        self, source: str = "local", corpus_pack: str = "sg_tort"
    ) -> List[HypotheticalEntry]:
        """Load corpus from local JSON file."""
        try:
            return await self._load_from_local(corpus_pack=corpus_pack)
        except Exception as e:
            logger.error("Failed to load corpus", source=source, error=str(e))
            raise CorpusServiceError(f"Failed to load corpus: {e}")

    async def _load_from_local(
        self, *, corpus_pack: str = "sg_tort"
    ) -> List[HypotheticalEntry]:
        """Load corpus from local JSON file."""
        corpus_paths = self._resolve_corpus_paths(corpus_pack)
        for corpus_path in corpus_paths:
            if not corpus_path.exists():
                raise CorpusServiceError(f"Local corpus file not found: {corpus_path}")

        try:
            entries: List[HypotheticalEntry] = []
            for corpus_path in corpus_paths:
                with open(corpus_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, list):
                    raise CorpusServiceError(
                        f"Corpus root must be a list: {corpus_path}"
                    )

                for i, item in enumerate(data):
                    raw_topics = item.get("topics", item.get("topic", []))
                    scope = self._entry_scope_from_item(item)
                    metadata = item.get("metadata", {})
                    if not isinstance(metadata, dict):
                        metadata = {}
                    metadata.setdefault("corpus_file", str(corpus_path))
                    for key in ("source", "license"):
                        if key in item and key not in metadata:
                            metadata[key] = item[key]
                    text = str(item.get("text", ""))
                    source_exam_context = self._entry_value(
                        item, metadata, "source_exam_context", {}
                    )
                    if not isinstance(source_exam_context, dict):
                        source_exam_context = {}
                    entry = HypotheticalEntry(
                        id=str(item.get("id", len(entries) + i)),
                        text=text,
                        topics=self._normalize_topics(raw_topics),
                        question_prompt=self._entry_value(
                            item, metadata, "question_prompt"
                        ),
                        fact_pattern=self._entry_value(
                            item, metadata, "fact_pattern", text
                        ),
                        issues_expected=self._preserve_string_list(
                            self._entry_value(item, metadata, "issues_expected", [])
                        ),
                        model_answer=self._entry_value(item, metadata, "model_answer"),
                        marking_rubric=self._entry_value(
                            item, metadata, "marking_rubric"
                        ),
                        difficulty=self._entry_value(item, metadata, "difficulty"),
                        time_limit_minutes=self._entry_value(
                            item, metadata, "time_limit_minutes"
                        ),
                        jurisdiction_notes=self._entry_value(
                            item, metadata, "jurisdiction_notes"
                        ),
                        answer_visibility=self._entry_value(
                            item, metadata, "answer_visibility", "hidden"
                        ),
                        source_exam_context=source_exam_context,
                        corpus_pack_key=scope["corpus_pack_key"],
                        jurisdiction=scope["jurisdiction"],
                        subject=scope["subject"],
                        subtopics=scope["subtopics"],
                        metadata=metadata,
                        created_at=item.get("created_at"),
                        updated_at=item.get("updated_at"),
                    )
                    entries.append(entry)

            logger.info(
                "Corpus loaded from local file",
                corpus_pack=corpus_pack,
                corpus_paths=[str(path) for path in corpus_paths],
                entries_count=len(entries),
            )
            return entries

        except json.JSONDecodeError as e:
            raise CorpusServiceError(f"Invalid JSON in corpus file: {e}")
        except Exception as e:
            raise CorpusServiceError(f"Error reading local corpus: {e}")

    async def save_corpus(
        self, entries: List[HypotheticalEntry], destination: str = "local"
    ) -> bool:
        """Save corpus to local JSON file."""
        try:
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
                entry.fact_pattern = entry.practice_fact_pattern
                entry.topics = self._normalize_topics(entry.topics)
                data.append(entry.model_dump(mode="json", exclude_none=True))

            with open(self._local_corpus_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            await self._invalidate_topic_cache()
            logger.info("Corpus saved to local file", entries_count=len(entries))
            return True

        except Exception as e:
            raise CorpusServiceError(f"Error saving to local file: {e}")

    async def query_relevant_hypotheticals(
        self, query: CorpusQuery
    ) -> List[HypotheticalEntry]:
        """
        Query corpus for relevant hypotheticals using semantic search.
        Falls back to simple topic matching if vector search unavailable.
        """
        try:
            if not self._corpus_indexed:
                maybe_awaitable = self._ensure_background_indexing()
                if inspect.isawaitable(maybe_awaitable):
                    await maybe_awaitable
                logger.info(
                    "Vector index not ready, using fallback search",
                    query_topics=query.topics,
                )

            if getattr(settings, "retrieval_mode", "dense") == "hybrid":
                corpus = await self.load_corpus(corpus_pack=query.corpus_pack)
                available_entries = [
                    entry
                    for entry in corpus
                    if entry.id not in query.exclude_ids
                    and self._entry_matches_scope(entry, query)
                    and self._entry_is_default_retrievable(entry)
                ]
                hybrid_documents = [
                    {
                        "id": entry.id,
                        "text": entry.text,
                        "topics": entry.topics,
                        "corpus_pack_key": entry.corpus_pack_key,
                        "jurisdiction": entry.jurisdiction,
                        "subject": entry.subject,
                        "subtopics": entry.subtopics,
                        "metadata": entry.metadata,
                    }
                    for entry in available_entries
                ]
                try:
                    hybrid_results = await self._vector_service.hybrid_search(
                        query_topics=query.topics,
                        corpus_documents=hybrid_documents,
                        corpus_pack=query.corpus_pack,
                        jurisdiction=query.jurisdiction,
                        subject=query.subject,
                        subtopics=query.subtopics,
                        n_results=query.sample_size,
                        exclude_ids=query.exclude_ids,
                    )
                    if hybrid_results:
                        relevant_entries = []
                        for result in hybrid_results:
                            metadata = result.get("metadata", {})
                            if not isinstance(metadata, dict):
                                metadata = {}
                            metadata = {
                                **metadata,
                                "retrieval_mode": result.get("retrieval_mode"),
                                "rrf_score": result.get("rrf_score"),
                                "dense_score": result.get("dense_score"),
                                "lexical_score": result.get("lexical_score"),
                            }
                            relevant_entries.append(
                                HypotheticalEntry(
                                    id=str(result["id"]),
                                    text=str(result.get("text", "")),
                                    topics=list(result.get("topics", [])),
                                    corpus_pack_key=str(
                                        result.get("corpus_pack_key", query.corpus_pack)
                                    ),
                                    jurisdiction=str(
                                        result.get("jurisdiction", query.jurisdiction)
                                    ),
                                    subject=str(result.get("subject", query.subject)),
                                    subtopics=list(result.get("subtopics", [])),
                                    metadata=metadata,
                                )
                            )
                        logger.info(
                            "Hybrid corpus retrieval completed",
                            query_topics=query.topics,
                            results_count=len(relevant_entries),
                        )
                        return relevant_entries
                except Exception as he:
                    logger.warning(
                        "Hybrid retrieval failed, falling back",
                        error=str(he),
                    )

            # Try semantic search first (ChromaDB + embeddings)
            if self._corpus_indexed:
                try:
                    results = await self._vector_service.semantic_search(
                        query_topics=query.topics,
                        corpus_pack=query.corpus_pack,
                        jurisdiction=query.jurisdiction,
                        subject=query.subject,
                        subtopics=query.subtopics,
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
                                corpus_pack_key=result.get(
                                    "corpus_pack_key", query.corpus_pack
                                ),
                                jurisdiction=result.get(
                                    "jurisdiction", query.jurisdiction
                                ),
                                subject=result.get("subject", query.subject),
                                subtopics=result.get("subtopics", []),
                                metadata=result["metadata"],
                            )
                            if not self._entry_is_default_retrievable(entry):
                                continue
                            relevant_entries.append(entry)

                        logger.info(
                            "Semantic search completed",
                            query_topics=query.topics,
                            results_count=len(relevant_entries),
                        )
                        return relevant_entries

                except (VectorServiceError, Exception) as ve:
                    logger.warning(
                        "Vector search failed, falling back to simple search",
                        error=str(ve),
                    )

            # Fallback: Simple topic overlap (original method)
            corpus = await self.load_corpus(corpus_pack=query.corpus_pack)
            available_entries = [
                entry
                for entry in corpus
                if entry.id not in query.exclude_ids
                and self._entry_matches_scope(entry, query)
                and self._entry_is_default_retrievable(entry)
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
            corpus_hash = (
                self._compute_current_corpus_hash()
                or self._compute_entries_hash(corpus)
            )

            indexed_hash = self._vector_service.get_indexed_corpus_hash()
            if indexed_hash and indexed_hash == corpus_hash:
                self._corpus_indexed = True
                self._indexed_corpus_hash = corpus_hash
                logger.info(
                    "Vector index already up to date; skipping rebuild",
                    corpus_hash=corpus_hash,
                )
                return

            # Convert to format expected by vector service
            hypotheticals_data = []
            for entry in corpus:
                if not self._entry_is_default_retrievable(entry):
                    continue
                hypotheticals_data.append(
                    {
                        "id": entry.id,
                        "text": entry.text,
                        "topics": entry.topics,
                        "corpus_pack_key": entry.corpus_pack_key,
                        "jurisdiction": entry.jurisdiction,
                        "subject": entry.subject,
                        "subtopics": entry.subtopics,
                        "metadata": entry.metadata,
                    }
                )

            # Index in vector database
            count = await self._vector_service.index_hypotheticals(
                hypotheticals_data,
                corpus_hash=corpus_hash,
            )
            self._corpus_indexed = True
            self._indexed_corpus_hash = corpus_hash

            logger.info(
                "Corpus indexed in vector database",
                count=count,
                corpus_hash=corpus_hash,
                previous_corpus_hash=indexed_hash,
            )

        except Exception as e:
            logger.warning("Failed to index corpus in vector database", error=str(e))
            self._corpus_indexed = False
            # Don't raise - allow fallback to simple search

    async def _ensure_background_indexing(self):
        """Schedule corpus indexing in background if not already running."""
        if self._corpus_indexed:
            current_hash = self._compute_current_corpus_hash()
            if (
                current_hash is not None
                and self._indexed_corpus_hash is not None
                and current_hash == self._indexed_corpus_hash
            ):
                return
        async with self._index_task_lock:
            if self._index_task and not self._index_task.done():
                return
            self._index_task = asyncio.create_task(self._run_background_index())

    async def _run_background_index(self):
        """Index corpus once in the background; safe under concurrent callers."""
        try:
            async with self._index_lock:
                if self._corpus_indexed:
                    return
                await self._index_corpus()
        finally:
            self._index_task = None

    async def extract_all_topics(
        self,
        *,
        corpus_pack: str = "sg_tort",
        jurisdiction: str = "sg",
        subject: str = "tort",
    ) -> List[str]:
        """Extract all unique topics from the corpus."""
        try:
            current_mtime = self._get_local_corpus_mtime(corpus_pack)
            use_cache = (
                corpus_pack == "sg_tort" and jurisdiction == "sg" and subject == "tort"
            )
            async with self._topics_cache_lock:
                if (
                    use_cache
                    and self._topics_cache is not None
                    and current_mtime is not None
                    and self._topics_cache_mtime == current_mtime
                ):
                    return list(self._topics_cache)

            corpus = await self.load_corpus(corpus_pack=corpus_pack)
            all_topics = set()
            query = CorpusQuery(
                topics=["negligence"],
                corpus_pack=corpus_pack,
                jurisdiction=jurisdiction,
                subject=subject,
            )

            for entry in corpus:
                if self._entry_matches_scope(
                    entry, query
                ) and self._entry_is_default_retrievable(entry):
                    all_topics.update(entry.topics)

            topics_list = sorted(list(all_topics))
            async with self._topics_cache_lock:
                if use_cache and current_mtime is not None:
                    self._topics_cache = topics_list
                    self._topics_cache_mtime = current_mtime
                elif use_cache:
                    self._topics_cache = None
                    self._topics_cache_mtime = None
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
            entry.topics = self._normalize_topics(entry.topics)
            entry.fact_pattern = entry.practice_fact_pattern

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
                    if key in {"topics", "topic"}:
                        setattr(entry, "topics", self._normalize_topics(value))
                        continue
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
            "total_entries": 0,
            "topics_count": 0,
            "ingestion": read_ingestion_health(),
        }

        try:
            if self._local_corpus_path.exists():
                corpus = await self.load_corpus("local", corpus_pack="sg_tort")
                health_status["local_corpus"] = True
                health_status["total_entries"] = len(corpus)
                health_status["topics_count"] = len(await self.extract_all_topics())
        except Exception as e:
            logger.error("Health check failed", error=str(e))

        return health_status


# Global corpus service instance
corpus_service = CorpusService()
