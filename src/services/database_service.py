"""
Database Service for persisting generation history using SQLite.
Lightweight, local-only storage perfect for internal tools.
"""

import asyncio
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)
SQLITE_BUSY_TIMEOUT_MS = 5000
SQLITE_BUSY_RETRY_ATTEMPTS = 3
SQLITE_BUSY_RETRY_BACKOFF_SECONDS = 0.1


class GenerationReport(BaseModel):
    """Structured generation issue report."""

    id: Optional[int] = None
    generation_id: int
    issue_types: List[str] = Field(default_factory=list)
    comment: Optional[str] = None
    correlation_id: Optional[str] = None
    is_locked: bool = True
    created_at: Optional[str] = None


class GenerationFeedback(BaseModel):
    """Follow-up feedback linked to a generation report."""

    id: Optional[int] = None
    report_id: int
    generation_id: int
    feedback_text: str
    created_at: Optional[str] = None


class StudentAttempt(BaseModel):
    """Student self-assessment linked to practice progress tracking."""

    id: Optional[int] = None
    generation_id: Optional[int] = None
    topics: List[str] = Field(default_factory=list)
    self_rating: Optional[int] = Field(default=None, ge=1, le=5)
    rubric_misses: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    elapsed_seconds: Optional[int] = Field(default=None, ge=0)
    attempted_at: Optional[str] = None
    created_at: Optional[str] = None


class DatabaseService:
    """Service for managing SQLite database for generation history."""

    def __init__(self, db_path: Optional[str] = None):
        from ..config import settings as app_settings

        self._db_path = Path(db_path or app_settings.database_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.Connection(str(self._db_path))
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {SQLITE_BUSY_TIMEOUT_MS}")
        return conn

    @contextmanager
    def _connection(self):
        """Yield a SQLite connection and always close it."""
        conn = self._get_connection()
        try:
            yield conn
        finally:
            conn.close()

    async def _run_in_thread(self, func, *args, **kwargs):
        """Execute blocking SQLite work off the event loop thread with busy retries."""
        attempt = 0
        while True:
            try:
                return await asyncio.to_thread(func, *args, **kwargs)
            except sqlite3.OperationalError as exc:
                message = str(exc).lower()
                if (
                    "database is locked" not in message
                    and "database is busy" not in message
                ):
                    raise
                attempt += 1
                if attempt >= SQLITE_BUSY_RETRY_ATTEMPTS:
                    raise
                await asyncio.sleep(SQLITE_BUSY_RETRY_BACKOFF_SECONDS * attempt)

    def _initialize_database(self):
        """Initialize database schema."""
        try:
            with self._connection() as conn:
                cursor = conn.cursor()

                # Create generation_history table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS generation_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        topics TEXT NOT NULL,
                        corpus_pack_key TEXT DEFAULT 'sg_tort',
                        jurisdiction TEXT DEFAULT 'sg',
                        subject TEXT DEFAULT 'tort',
                        subtopics TEXT DEFAULT '[]',
                        law_domain TEXT,
                        number_parties INTEGER,
                        complexity_level TEXT,
                        hypothetical TEXT,
                        analysis TEXT,
                        generation_time REAL,
                        validation_passed BOOLEAN,
                        quality_score REAL,
                        quality_gate_failure_reasons TEXT,
                        request_data TEXT,
                        response_data TEXT,
                        parent_generation_id INTEGER,
                        retry_reason TEXT,
                        retry_attempt INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create index on timestamp for faster queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_generation_history_timestamp
                    ON generation_history(timestamp DESC)
                """)

                # Create index on topics for searching
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_topics
                    ON generation_history(topics)
                """)

                self._ensure_generation_history_lineage_columns(cursor)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_generation_history_parent_generation_id
                    ON generation_history(parent_generation_id)
                    """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS generation_reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        generation_id INTEGER NOT NULL,
                        issue_types TEXT NOT NULL,
                        comment TEXT,
                        correlation_id TEXT,
                        is_locked BOOLEAN NOT NULL DEFAULT 1,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (generation_id) REFERENCES generation_history(id) ON DELETE CASCADE
                    )
                """)

                self._ensure_generation_reports_columns(cursor)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_generation_reports_generation_id
                    ON generation_reports(generation_id)
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS generation_feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        report_id INTEGER NOT NULL,
                        generation_id INTEGER NOT NULL,
                        feedback_text TEXT NOT NULL,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (report_id) REFERENCES generation_reports(id) ON DELETE CASCADE,
                        FOREIGN KEY (generation_id) REFERENCES generation_history(id) ON DELETE CASCADE
                    )
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_generation_feedback_report_id
                    ON generation_feedback(report_id)
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS student_attempts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        generation_id INTEGER,
                        attempted_at TEXT NOT NULL,
                        topics TEXT NOT NULL,
                        self_rating INTEGER,
                        rubric_misses TEXT NOT NULL DEFAULT '[]',
                        notes TEXT,
                        elapsed_seconds INTEGER,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (generation_id) REFERENCES generation_history(id) ON DELETE SET NULL
                    )
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_student_attempts_attempted_at
                    ON student_attempts(attempted_at DESC)
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_student_attempts_generation_id
                    ON student_attempts(generation_id)
                """)

                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS migration_state (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                    """)

                conn.commit()

            logger.info("Database initialized", db_path=str(self._db_path))

        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            raise

    def _ensure_generation_history_lineage_columns(self, cursor: sqlite3.Cursor):
        """Backfill lineage columns for existing databases created before lineage support."""
        cursor.execute("PRAGMA table_info(generation_history)")
        columns = {row["name"] for row in cursor.fetchall()}

        if "parent_generation_id" not in columns:
            cursor.execute(
                "ALTER TABLE generation_history ADD COLUMN parent_generation_id INTEGER"
            )
        if "retry_reason" not in columns:
            cursor.execute(
                "ALTER TABLE generation_history ADD COLUMN retry_reason TEXT"
            )
        if "retry_attempt" not in columns:
            cursor.execute(
                "ALTER TABLE generation_history ADD COLUMN retry_attempt INTEGER DEFAULT 0"
            )
        if "quality_gate_failure_reasons" not in columns:
            cursor.execute(
                "ALTER TABLE generation_history ADD COLUMN quality_gate_failure_reasons TEXT"
            )
        if "corpus_pack_key" not in columns:
            cursor.execute(
                "ALTER TABLE generation_history ADD COLUMN corpus_pack_key TEXT DEFAULT 'sg_tort'"
            )
        if "jurisdiction" not in columns:
            cursor.execute(
                "ALTER TABLE generation_history ADD COLUMN jurisdiction TEXT DEFAULT 'sg'"
            )
        if "subject" not in columns:
            cursor.execute(
                "ALTER TABLE generation_history ADD COLUMN subject TEXT DEFAULT 'tort'"
            )
        if "subtopics" not in columns:
            cursor.execute(
                "ALTER TABLE generation_history ADD COLUMN subtopics TEXT DEFAULT '[]'"
            )

    def _ensure_generation_reports_columns(self, cursor: sqlite3.Cursor):
        """Backfill report columns for existing databases."""
        cursor.execute("PRAGMA table_info(generation_reports)")
        columns = {row["name"] for row in cursor.fetchall()}
        if "correlation_id" not in columns:
            cursor.execute(
                "ALTER TABLE generation_reports ADD COLUMN correlation_id TEXT"
            )

    def _decode_json_payload(
        self,
        value: Any,
        *,
        field_name: str,
        fallback: Any,
    ) -> Any:
        """Defensively decode persisted JSON payloads with fallback on corruption."""
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            logger.warning(
                "Failed to decode persisted JSON payload",
                field_name=field_name,
            )
            return fallback

    def _safe_json_decode(
        self,
        value: Any,
        *,
        field_name: str,
        fallback: Any,
    ) -> Any:
        """Backward-compatible alias for JSON decoding helper."""
        return self._decode_json_payload(
            value,
            field_name=field_name,
            fallback=fallback,
        )

    def _legacy_history_record_to_payload(
        self, record: Dict[str, Any]
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """Convert old data/history.json record format to request/response payloads."""
        config = record.get("config", {}) if isinstance(record, dict) else {}
        topics = config.get("topics")
        if not topics:
            topic = config.get("topic")
            topics = [topic] if topic else ["negligence"]
        if not isinstance(topics, list):
            topics = [str(topics)]

        raw_parties = config.get("parties", 3)
        try:
            number_parties = int(raw_parties)
        except (TypeError, ValueError):
            number_parties = 3

        raw_score = record.get("validation_score", record.get("score", 0.0))
        try:
            quality_score = float(raw_score)
        except (TypeError, ValueError):
            quality_score = 0.0

        timestamp = record.get("timestamp") or datetime.utcnow().isoformat()

        request_data = {
            "topics": topics,
            "law_domain": "tort",
            "corpus_pack": "sg_tort",
            "jurisdiction": "sg",
            "subject": "tort",
            "subtopics": [],
            "number_parties": number_parties,
            "complexity_level": str(config.get("complexity", "intermediate")),
            "method": config.get("method", "pure_llm"),
            "provider": config.get("provider"),
            "model": config.get("model"),
        }
        response_data = {
            "hypothetical": record.get("hypothetical", ""),
            "analysis": record.get("analysis", ""),
            "model_answer": record.get("model_answer", ""),
            "generation_time": record.get("generation_time", 0.0),
            "validation_results": {
                "passed": quality_score >= 7.0,
                "quality_score": quality_score,
            },
            "metadata": {
                "generation_timestamp": timestamp,
            },
        }
        return request_data, response_data

    @staticmethod
    def _extract_quality_gate_failure_reasons(
        response_data: Dict[str, Any],
    ) -> List[str]:
        """Extract normalized quality-gate failure reason codes from response payload."""
        validation_results = response_data.get("validation_results") or {}
        adherence = validation_results.get("adherence_check") or {}
        quality_gate = adherence.get("quality_gate") or {}
        failed_checks = quality_gate.get("failed_checks") or []

        reasons: List[str] = []
        for reason in failed_checks:
            text = str(reason).strip().lower()
            if not text:
                continue
            reasons.append(text.replace(" ", "_"))

        if (not validation_results.get("passed", True)) and not reasons:
            reasons.append("validation_failed")

        # Preserve order while deduplicating.
        deduped: List[str] = []
        seen = set()
        for reason in reasons:
            if reason in seen:
                continue
            seen.add(reason)
            deduped.append(reason)
        return deduped

    def _row_to_history_record(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Normalize a generation_history row into legacy-compatible history shape."""
        request_data = self._decode_json_payload(
            row["request_data"],
            field_name="request_data",
            fallback={},
        )
        response_data = self._decode_json_payload(
            row["response_data"],
            field_name="response_data",
            fallback={},
        )
        topics = request_data.get("topics", [])
        topic = topics[0] if topics else ""

        raw_parties = request_data.get("number_parties", 3)
        try:
            parties = int(raw_parties)
        except (TypeError, ValueError):
            parties = 3

        complexity_value: Any = request_data.get("complexity_level", "intermediate")
        try:
            complexity_value = int(complexity_value)
        except (TypeError, ValueError):
            pass

        quality_score = (
            response_data.get("validation_results", {}).get("quality_score")
            or row["quality_score"]
            or 0.0
        )
        try:
            quality_score = float(quality_score)
        except (TypeError, ValueError):
            quality_score = 0.0

        failure_reason_codes = self._extract_quality_gate_failure_reasons(response_data)
        if row["quality_gate_failure_reasons"]:
            try:
                stored_codes = json.loads(row["quality_gate_failure_reasons"])
            except (TypeError, json.JSONDecodeError):
                stored_codes = []
            if isinstance(stored_codes, list):
                for code in stored_codes:
                    normalized = str(code).strip().lower()
                    if normalized and normalized not in failure_reason_codes:
                        failure_reason_codes.append(normalized)

        return {
            "generation_id": row["id"],
            "timestamp": row["timestamp"],
            "config": {
                "topic": topic,
                "topics": topics,
                "provider": request_data.get("provider"),
                "model": request_data.get("model"),
                "complexity": complexity_value,
                "parties": parties,
                "method": request_data.get("method", "pure_llm"),
                "practice_mode": request_data.get("practice_mode", "issue_spotting"),
            },
            "hypothetical": response_data.get("hypothetical", ""),
            "analysis": response_data.get("analysis", ""),
            "model_answer": response_data.get("model_answer", ""),
            "practice": response_data.get("metadata", {}).get("practice", {}),
            "validation_score": quality_score,
            "quality_gate_failure_reasons": failure_reason_codes,
            "parent_generation_id": row["parent_generation_id"],
            "retry_reason": row["retry_reason"],
            "retry_attempt": row["retry_attempt"] or 0,
        }

    @staticmethod
    def _normalize_attempt_topics(topics: List[str]) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for topic in topics or []:
            text = " ".join(str(topic).strip().lower().replace("_", " ").split())
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        if not normalized:
            raise ValueError("student attempt requires at least one topic")
        return normalized

    @staticmethod
    def _normalize_rubric_misses(rubric_misses: List[str]) -> List[str]:
        normalized: List[str] = []
        seen = set()
        for miss in rubric_misses or []:
            text = "_".join(str(miss).strip().lower().replace("-", " ").split())
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    @staticmethod
    def _parse_progress_timestamp(value: Any) -> Optional[datetime]:
        if not value:
            return None
        text = str(value).strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            return None

    @staticmethod
    def _utcnow_naive() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    def _row_to_student_attempt(self, row: sqlite3.Row) -> Dict[str, Any]:
        attempt = {
            "id": row["id"],
            "generation_id": row["generation_id"],
            "topics": self._safe_json_decode(
                row["topics"], field_name="student_attempt_topics", fallback=[]
            ),
            "self_rating": row["self_rating"],
            "rubric_misses": self._safe_json_decode(
                row["rubric_misses"],
                field_name="student_attempt_rubric_misses",
                fallback=[],
            ),
            "notes": row["notes"],
            "elapsed_seconds": row["elapsed_seconds"],
            "attempted_at": row["attempted_at"],
            "created_at": row["created_at"],
        }
        if "generation_timestamp" in row.keys() and row["generation_timestamp"]:
            response_data = self._safe_json_decode(
                row["response_data"], field_name="response_data", fallback={}
            )
            attempt["generation"] = {
                "timestamp": row["generation_timestamp"],
                "hypothetical": response_data.get("hypothetical", ""),
            }
        return attempt

    def _aggregate_topic_progress(
        self, attempts: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        topic_rows: Dict[str, Dict[str, Any]] = {}
        for attempt in attempts:
            topics = self._normalize_attempt_topics(attempt.get("topics", []))
            rating = attempt.get("self_rating")
            misses = self._normalize_rubric_misses(attempt.get("rubric_misses", []))
            attempted_at = attempt.get("attempted_at")
            attempted_dt = self._parse_progress_timestamp(attempted_at)
            is_weak = bool(misses) or (rating is not None and int(rating) <= 2)
            for topic in topics:
                row = topic_rows.setdefault(
                    topic,
                    {
                        "topic": topic,
                        "attempt_count": 0,
                        "weak_attempt_count": 0,
                        "rating_total": 0,
                        "rating_count": 0,
                        "last_self_rating": None,
                        "last_attempted_at": None,
                        "_last_attempted_dt": None,
                        "rubric_miss_counts": {},
                    },
                )
                row["attempt_count"] += 1
                if rating is not None:
                    row["rating_total"] += int(rating)
                    row["rating_count"] += 1
                if is_weak:
                    row["weak_attempt_count"] += 1
                for miss in misses:
                    row["rubric_miss_counts"][miss] = (
                        row["rubric_miss_counts"].get(miss, 0) + 1
                    )
                if attempted_dt is None:
                    continue
                if (
                    row["_last_attempted_dt"] is None
                    or attempted_dt > row["_last_attempted_dt"]
                ):
                    row["_last_attempted_dt"] = attempted_dt
                    row["last_attempted_at"] = attempted_at
                    row["last_self_rating"] = rating

        progress: List[Dict[str, Any]] = []
        for row in topic_rows.values():
            rating_count = row.pop("rating_count")
            rating_total = row.pop("rating_total")
            row.pop("_last_attempted_dt", None)
            average_rating = (
                round(rating_total / rating_count, 2) if rating_count else None
            )
            miss_total = sum(row["rubric_miss_counts"].values())
            weak_rate = row["weak_attempt_count"] / row["attempt_count"]
            rating_penalty = (
                max(0.0, (5.0 - average_rating) / 4.0)
                if average_rating is not None
                else 0.0
            )
            miss_penalty = min(1.0, miss_total / max(1, row["attempt_count"] * 2))
            row["average_self_rating"] = average_rating
            row["repeated_weak_topic"] = row["weak_attempt_count"] >= 2
            row["rubric_miss_counts"] = dict(
                sorted(
                    row["rubric_miss_counts"].items(),
                    key=lambda item: (-item[1], item[0]),
                )
            )
            row["weakness_score"] = round(
                (weak_rate * 0.5) + (rating_penalty * 0.3) + (miss_penalty * 0.2),
                3,
            )
            if row["weak_attempt_count"] or (
                average_rating is not None and average_rating <= 3
            ):
                progress.append(row)

        progress.sort(
            key=lambda row: (
                -row["weakness_score"],
                row["last_attempted_at"] or "",
                row["topic"],
            )
        )
        return progress

    def _next_review_at(self, topic_row: Dict[str, Any]) -> str:
        last_attempt = self._parse_progress_timestamp(
            topic_row.get("last_attempted_at")
        )
        if last_attempt is None:
            return self._utcnow_naive().isoformat(timespec="seconds")
        rating = topic_row.get("average_self_rating")
        has_misses = bool(topic_row.get("rubric_miss_counts"))
        if (
            topic_row.get("repeated_weak_topic")
            or has_misses
            or (rating is not None and rating <= 2)
        ):
            interval_days = 1
        elif rating is not None and rating <= 3:
            interval_days = 3
        else:
            interval_days = 7
        return (last_attempt + timedelta(days=interval_days)).isoformat(
            timespec="seconds"
        )

    async def migrate_legacy_history_json(
        self, history_path: str = "data/history.json"
    ) -> int:
        """One-time migration from legacy JSON history to SQLite rows."""
        migration_key = "history_json_to_sqlite_v1"
        try:

            def _read_migration_state():
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT value FROM migration_state WHERE key = ?",
                        (migration_key,),
                    )
                    return cursor.fetchone()

            migrated_row = await self._run_in_thread(_read_migration_state)
            if migrated_row and migrated_row["value"] == "1":
                return 0

            path = Path(history_path)
            migrated_count = 0
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as handle:
                        history_records = json.load(handle)
                except Exception as e:
                    logger.error("Failed to load legacy history JSON", error=str(e))
                    history_records = []

                if isinstance(history_records, list):
                    for record in history_records:
                        if not isinstance(record, dict):
                            continue
                        (
                            request_data,
                            response_data,
                        ) = self._legacy_history_record_to_payload(record)
                        try:
                            await self.save_generation(
                                request_data=request_data,
                                response_data=response_data,
                                parent_generation_id=record.get("parent_generation_id"),
                                retry_reason=record.get("retry_reason"),
                                retry_attempt=record.get("retry_attempt", 0),
                            )
                            migrated_count += 1
                        except Exception as e:
                            logger.warning(
                                "Skipping invalid legacy history record",
                                error=str(e),
                            )

            def _write_migration_state():
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO migration_state (key, value, updated_at)
                        VALUES (?, '1', CURRENT_TIMESTAMP)
                        ON CONFLICT(key) DO UPDATE SET
                            value = excluded.value,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (migration_key,),
                    )
                    conn.commit()

            await self._run_in_thread(_write_migration_state)

            logger.info(
                "Legacy history migration completed",
                migrated_count=migrated_count,
                history_path=history_path,
            )
            return migrated_count
        except Exception as e:
            logger.error("Legacy history migration failed", error=str(e))
            return 0

    async def save_generation(
        self,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any],
        parent_generation_id: Optional[int] = None,
        retry_reason: Optional[str] = None,
        retry_attempt: int = 0,
        correlation_id: Optional[str] = None,
    ) -> int:
        """
        Save a generation to the database.

        Returns:
            The ID of the inserted record
        """
        try:

            def _op() -> int:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    try:
                        normalized_retry_attempt = max(0, int(retry_attempt))
                    except (TypeError, ValueError):
                        normalized_retry_attempt = 0
                    failure_reason_codes = self._extract_quality_gate_failure_reasons(
                        response_data
                    )

                    cursor.execute(
                        """
                        INSERT INTO generation_history (
                            timestamp, topics, law_domain, number_parties, complexity_level,
                            corpus_pack_key, jurisdiction, subject, subtopics,
                            hypothetical, analysis, generation_time, validation_passed,
                            quality_score, quality_gate_failure_reasons, request_data,
                            response_data, parent_generation_id, retry_reason, retry_attempt
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            response_data.get("metadata", {}).get(
                                "generation_timestamp", datetime.utcnow().isoformat()
                            ),
                            json.dumps(request_data.get("topics", [])),
                            request_data.get("law_domain"),
                            request_data.get("number_parties"),
                            request_data.get("complexity_level"),
                            request_data.get("corpus_pack", "sg_tort"),
                            request_data.get("jurisdiction", "sg"),
                            request_data.get(
                                "subject", request_data.get("law_domain", "tort")
                            ),
                            json.dumps(request_data.get("subtopics", [])),
                            response_data.get("hypothetical", ""),
                            response_data.get("analysis", ""),
                            response_data.get("generation_time", 0.0),
                            response_data.get("validation_results", {}).get(
                                "passed", False
                            ),
                            response_data.get("validation_results", {}).get(
                                "quality_score", 0.0
                            ),
                            json.dumps(failure_reason_codes),
                            json.dumps(request_data),
                            json.dumps(response_data),
                            parent_generation_id,
                            retry_reason,
                            normalized_retry_attempt,
                        ),
                    )
                    record_id = cursor.lastrowid
                    conn.commit()
                    return int(record_id)

            record_id = await self._run_in_thread(_op)

            logger.info(
                "Generation saved to database",
                id=record_id,
                correlation_id=correlation_id,
            )
            return record_id

        except Exception as e:
            logger.error(
                "Failed to save generation",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise

    async def get_recent_generations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent generations from database.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of generation records
        """
        try:

            def _op() -> List[Dict[str, Any]]:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT
                            timestamp, request_data, response_data
                        FROM generation_history
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """,
                        (limit,),
                    )
                    rows = cursor.fetchall()
                generations = []
                for row in rows:
                    generations.append(
                        {
                            "timestamp": row["timestamp"],
                            "request": self._decode_json_payload(
                                row["request_data"],
                                field_name="request_data",
                                fallback={},
                            ),
                            "response": self._decode_json_payload(
                                row["response_data"],
                                field_name="response_data",
                                fallback={},
                            ),
                        }
                    )
                return generations

            generations = await self._run_in_thread(_op)
            logger.info("Retrieved recent generations", count=len(generations))
            return generations

        except Exception as e:
            logger.error("Failed to get recent generations", error=str(e))
            return []

    async def get_generation_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Backward-compatible alias for recent generation history."""
        return await self.get_recent_generations(limit)

    async def get_history_records(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Return history in legacy-compatible record shape, sourced from SQLite."""
        try:

            def _op() -> List[Dict[str, Any]]:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT
                            id,
                            timestamp,
                            request_data,
                            response_data,
                            quality_score,
                            quality_gate_failure_reasons,
                            parent_generation_id,
                            retry_reason,
                            retry_attempt
                        FROM generation_history
                        ORDER BY timestamp DESC
                        LIMIT ?
                        """,
                        (limit,),
                    )
                    rows = cursor.fetchall()
                return [self._row_to_history_record(row) for row in reversed(rows)]

            return await self._run_in_thread(_op)
        except Exception as e:
            logger.error("Failed to get history records", error=str(e))
            return []

    async def get_generation_count(self) -> int:
        """Count total persisted generations."""
        try:

            def _op() -> int:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) AS count FROM generation_history")
                    row = cursor.fetchone()
                    return int(row["count"] if row else 0)

            return await self._run_in_thread(_op)
        except Exception as e:
            logger.error("Failed to count generations", error=str(e))
            return 0

    async def get_history_record_by_index(
        self, history_index: int
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single history record by chronological index (0 = oldest)."""
        try:

            def _op() -> Optional[Dict[str, Any]]:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT
                            id,
                            timestamp,
                            request_data,
                            response_data,
                            quality_score,
                            quality_gate_failure_reasons,
                            parent_generation_id,
                            retry_reason,
                            retry_attempt
                        FROM generation_history
                        ORDER BY timestamp ASC
                        LIMIT 1 OFFSET ?
                        """,
                        (history_index,),
                    )
                    row = cursor.fetchone()
                if not row:
                    return None
                return self._row_to_history_record(row)

            return await self._run_in_thread(_op)
        except Exception as e:
            logger.error("Failed to get history record by index", error=str(e))
            return None

    async def get_generation_by_id(
        self, generation_id: int
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single generation row by primary key."""
        try:

            def _op() -> Optional[Dict[str, Any]]:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT id, timestamp, request_data, response_data,
                               parent_generation_id, retry_reason, retry_attempt,
                               quality_gate_failure_reasons
                        FROM generation_history
                        WHERE id = ?
                        """,
                        (generation_id,),
                    )
                    row = cursor.fetchone()
                if not row:
                    return None
                return {
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "request": self._decode_json_payload(
                        row["request_data"],
                        field_name="request_data",
                        fallback={},
                    ),
                    "response": self._decode_json_payload(
                        row["response_data"],
                        field_name="response_data",
                        fallback={},
                    ),
                    "parent_generation_id": row["parent_generation_id"],
                    "retry_reason": row["retry_reason"],
                    "retry_attempt": row["retry_attempt"] or 0,
                    "quality_gate_failure_reasons": self._safe_json_decode(
                        row["quality_gate_failure_reasons"] or "[]",
                        field_name="quality_gate_failure_reasons",
                        fallback=[],
                    ),
                }

            return await self._run_in_thread(_op)
        except Exception as e:
            logger.error("Failed to get generation by id", error=str(e))
            return None

    async def save_generation_report(self, report: GenerationReport) -> int:
        """Persist a report linked to a generation row."""
        try:

            def _op() -> int:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO generation_reports (
                            generation_id, issue_types, comment, correlation_id, is_locked
                        ) VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            report.generation_id,
                            json.dumps(report.issue_types),
                            report.comment,
                            report.correlation_id,
                            bool(report.is_locked),
                        ),
                    )
                    report_id = cursor.lastrowid
                    conn.commit()
                    return int(report_id)

            report_id = await self._run_in_thread(_op)
            logger.info("Generation report saved", report_id=report_id)
            return report_id
        except Exception as e:
            logger.error("Failed to save generation report", error=str(e))
            raise

    async def save_generation_feedback(self, feedback: GenerationFeedback) -> int:
        """Persist follow-up feedback for a report."""
        try:

            def _op() -> int:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO generation_feedback (
                            report_id, generation_id, feedback_text
                        ) VALUES (?, ?, ?)
                        """,
                        (
                            feedback.report_id,
                            feedback.generation_id,
                            feedback.feedback_text,
                        ),
                    )
                    feedback_id = cursor.lastrowid
                    conn.commit()
                    return int(feedback_id)

            feedback_id = await self._run_in_thread(_op)
            logger.info("Generation feedback saved", feedback_id=feedback_id)
            return feedback_id
        except Exception as e:
            logger.error("Failed to save generation feedback", error=str(e))
            raise

    async def get_generation_reports(
        self, generation_id: int
    ) -> List[GenerationReport]:
        """Fetch reports associated with a generation."""
        try:

            def _op() -> List[GenerationReport]:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT id, generation_id, issue_types, comment, correlation_id, is_locked, created_at
                        FROM generation_reports
                        WHERE generation_id = ?
                        ORDER BY created_at ASC
                        """,
                        (generation_id,),
                    )
                    rows = cursor.fetchall()
                return [
                    GenerationReport(
                        id=row["id"],
                        generation_id=row["generation_id"],
                        issue_types=self._safe_json_decode(
                            row["issue_types"], field_name="issue_types", fallback=[]
                        ),
                        comment=row["comment"],
                        correlation_id=row["correlation_id"],
                        is_locked=bool(row["is_locked"]),
                        created_at=row["created_at"],
                    )
                    for row in rows
                ]

            return await self._run_in_thread(_op)
        except Exception as e:
            logger.error("Failed to load generation reports", error=str(e))
            return []

    async def get_report_feedback(self, report_id: int) -> List[GenerationFeedback]:
        """Fetch feedback rows linked to a specific report."""
        try:

            def _op() -> List[GenerationFeedback]:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT id, report_id, generation_id, feedback_text, created_at
                        FROM generation_feedback
                        WHERE report_id = ?
                        ORDER BY created_at ASC
                        """,
                        (report_id,),
                    )
                    rows = cursor.fetchall()
                return [
                    GenerationFeedback(
                        id=row["id"],
                        report_id=row["report_id"],
                        generation_id=row["generation_id"],
                        feedback_text=row["feedback_text"],
                        created_at=row["created_at"],
                    )
                    for row in rows
                ]

            return await self._run_in_thread(_op)
        except Exception as e:
            logger.error("Failed to load report feedback", error=str(e))
            return []

    async def build_regeneration_feedback_context(self, generation_id: int) -> str:
        """Build immutable feedback context from stored reports and feedback."""
        reports = await self.get_generation_reports(generation_id)
        if not reports:
            return ""

        segments: List[str] = []
        for report in reports:
            report_parts: List[str] = []
            if report.issue_types:
                report_parts.append("Issue types: " + ", ".join(report.issue_types))
            if report.comment:
                report_parts.append("Reporter comment: " + report.comment)
            if report.id is not None:
                feedback_rows = await self.get_report_feedback(report.id)
                for feedback in feedback_rows:
                    report_parts.append("Feedback: " + feedback.feedback_text)
            if report_parts:
                segments.append("; ".join(report_parts))

        return " | ".join(segments)

    async def save_student_attempt(self, attempt: StudentAttempt) -> int:
        """Persist student attempt/self-rating progress data."""
        topics = self._normalize_attempt_topics(attempt.topics)
        rubric_misses = self._normalize_rubric_misses(attempt.rubric_misses)
        attempted_at = (
            attempt.attempted_at or self._utcnow_naive().isoformat()
        ).strip()
        if self._parse_progress_timestamp(attempted_at) is None:
            raise ValueError("attempted_at must be an ISO timestamp")

        try:

            def _op() -> int:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO student_attempts (
                            generation_id, attempted_at, topics, self_rating,
                            rubric_misses, notes, elapsed_seconds
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            attempt.generation_id,
                            attempted_at,
                            json.dumps(topics),
                            attempt.self_rating,
                            json.dumps(rubric_misses),
                            attempt.notes,
                            attempt.elapsed_seconds,
                        ),
                    )
                    attempt_id = cursor.lastrowid
                    conn.commit()
                    return int(attempt_id)

            attempt_id = await self._run_in_thread(_op)
            logger.info("Student attempt saved", attempt_id=attempt_id)
            return attempt_id
        except Exception as e:
            logger.error("Failed to save student attempt", error=str(e))
            raise

    async def get_student_attempts(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Return recent student attempts with linked generation context."""
        safe_limit = max(1, min(int(limit), 500))
        try:

            def _op() -> List[Dict[str, Any]]:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT
                            a.id,
                            a.generation_id,
                            a.attempted_at,
                            a.topics,
                            a.self_rating,
                            a.rubric_misses,
                            a.notes,
                            a.elapsed_seconds,
                            a.created_at,
                            h.timestamp AS generation_timestamp,
                            h.response_data
                        FROM student_attempts a
                        LEFT JOIN generation_history h ON h.id = a.generation_id
                        ORDER BY a.attempted_at DESC, a.id DESC
                        LIMIT ?
                        """,
                        (safe_limit,),
                    )
                    return [
                        self._row_to_student_attempt(row) for row in cursor.fetchall()
                    ]

            return await self._run_in_thread(_op)
        except Exception as e:
            logger.error("Failed to get student attempts", error=str(e))
            return []

    async def get_weak_topics(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Aggregate repeated weak topics from student attempts."""
        safe_limit = max(1, min(int(limit), 100))
        attempts = await self.get_student_attempts(limit=500)
        return self._aggregate_topic_progress(attempts)[:safe_limit]

    async def get_spaced_repetition_queue(
        self, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Return topic review queue derived from weak-topic history."""
        safe_limit = max(1, min(int(limit), 100))
        now = self._utcnow_naive()
        queue = []
        for topic in await self.get_weak_topics(limit=100):
            next_review_at = self._next_review_at(topic)
            review_dt = self._parse_progress_timestamp(next_review_at)
            top_miss = next(iter(topic["rubric_miss_counts"]), None)
            queue.append(
                {
                    "topic": topic["topic"],
                    "next_review_at": next_review_at,
                    "due_now": review_dt is None or review_dt <= now,
                    "weakness_score": topic["weakness_score"],
                    "attempt_count": topic["attempt_count"],
                    "weak_attempt_count": topic["weak_attempt_count"],
                    "average_self_rating": topic["average_self_rating"],
                    "repeated_weak_topic": topic["repeated_weak_topic"],
                    "suggested_action": (
                        f"retry rubric criterion: {top_miss}"
                        if top_miss
                        else "retry issue spotting under timed conditions"
                    ),
                }
            )
        queue.sort(
            key=lambda item: (
                not item["due_now"],
                item["next_review_at"],
                -item["weakness_score"],
                item["topic"],
            )
        )
        return queue[:safe_limit]

    async def export_study_plan(self, days: int = 7) -> Dict[str, Any]:
        """Export a simple markdown study plan from the spaced repetition queue."""
        safe_days = max(1, min(int(days), 30))
        generated_at = self._utcnow_naive()
        queue = await self.get_spaced_repetition_queue(limit=100)
        items = []
        if queue:
            for index, queue_item in enumerate(queue):
                day_index = index % safe_days
                target_date = (
                    (generated_at + timedelta(days=day_index)).date().isoformat()
                )
                items.append(
                    {
                        "date": target_date,
                        "topic": queue_item["topic"],
                        "suggested_action": queue_item["suggested_action"],
                        "weakness_score": queue_item["weakness_score"],
                    }
                )
        markdown_lines = [
            "# Study plan",
            "",
            f"Generated: {generated_at.isoformat(timespec='seconds')}",
            "",
        ]
        if not items:
            markdown_lines.append("No weak topics recorded.")
        else:
            for item in items:
                markdown_lines.append(
                    f"- {item['date']}: {item['topic']} - {item['suggested_action']}"
                )
        return {
            "generated_at": generated_at.isoformat(timespec="seconds"),
            "days": safe_days,
            "items": items,
            "markdown": "\n".join(markdown_lines),
        }

    async def get_progress_summary(self, limit: int = 10) -> Dict[str, Any]:
        """Return attempt history, weak topics, spaced queue, and study plan."""
        safe_limit = max(1, min(int(limit), 100))
        return {
            "recent_attempts": await self.get_student_attempts(limit=safe_limit),
            "weak_topics": await self.get_weak_topics(limit=safe_limit),
            "spaced_repetition_queue": await self.get_spaced_repetition_queue(
                limit=safe_limit
            ),
            "study_plan": await self.export_study_plan(days=7),
        }

    async def update_generation_report_comment(self, report_id: int, comment: str):
        """Generation reports are append-only and cannot be edited."""
        raise PermissionError(
            f"Generation report {report_id} is immutable; create a new report instead"
        )

    async def delete_generation_report(self, report_id: int):
        """Generation reports are append-only and cannot be deleted."""
        raise PermissionError(
            f"Generation report {report_id} is immutable; deletion is not allowed"
        )

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get generation statistics from database.

        Returns:
            Dict with statistics (total, avg_time, success_rate, etc.)
        """
        try:

            def _op() -> Dict[str, Any]:
                with self._connection() as conn:
                    cursor = conn.cursor()

                    cursor.execute("""
                        SELECT
                            COUNT(*) as total_generations,
                            AVG(generation_time) as avg_generation_time,
                            AVG(CASE WHEN validation_passed THEN 1.0 ELSE 0.0 END) as success_rate,
                            AVG(quality_score) as avg_quality_score,
                            MIN(timestamp) as first_generation,
                            MAX(timestamp) as last_generation
                        FROM generation_history
                    """)
                    row = cursor.fetchone()

                    cursor.execute("""
                        SELECT
                            topics, COUNT(*) as count
                        FROM generation_history
                        GROUP BY topics
                        ORDER BY count DESC
                        LIMIT 10
                    """)
                    topic_rows = cursor.fetchall()

                    cursor.execute("""
                        SELECT response_data
                        FROM generation_history
                        WHERE response_data IS NOT NULL
                        """)
                    latency_rows = cursor.fetchall()

                latency_keys = [
                    "topic_extraction_time_ms",
                    "retrieval_time_ms",
                    "generation_time_ms",
                    "validation_time_ms",
                    "analysis_time_ms",
                ]
                latency_samples: Dict[str, List[float]] = {
                    key: [] for key in latency_keys
                }
                for latency_row in latency_rows:
                    response_payload = self._decode_json_payload(
                        latency_row["response_data"],
                        field_name="response_data",
                        fallback={},
                    )
                    if not isinstance(response_payload, dict):
                        continue
                    metrics = response_payload.get("metadata", {}).get(
                        "latency_metrics", {}
                    )
                    if not isinstance(metrics, dict):
                        continue
                    for key in latency_keys:
                        value = metrics.get(key)
                        if isinstance(value, (int, float)):
                            latency_samples[key].append(float(value))

                latency_metrics: Dict[str, Dict[str, Any]] = {}
                for key, samples in latency_samples.items():
                    average_ms = (
                        round(sum(samples) / len(samples), 2) if samples else 0.0
                    )
                    latency_metrics[key] = {
                        "average_ms": average_ms,
                        "samples": len(samples),
                    }

                return {
                    "total_generations": row["total_generations"] or 0,
                    "average_generation_time": row["avg_generation_time"] or 0.0,
                    "success_rate": (row["success_rate"] or 0.0) * 100,
                    "average_quality_score": row["avg_quality_score"] or 0.0,
                    "first_generation": row["first_generation"],
                    "last_generation": row["last_generation"],
                    "latency_metrics": latency_metrics,
                    "popular_topics": [
                        {
                            "topics": self._safe_json_decode(
                                t["topics"], field_name="topics", fallback=[]
                            ),
                            "count": t["count"],
                        }
                        for t in topic_rows
                    ],
                }

            stats = await self._run_in_thread(_op)
            logger.info("Retrieved statistics", total=stats["total_generations"])
            return stats

        except Exception as e:
            logger.error("Failed to get statistics", error=str(e))
            return {
                "total_generations": 0,
                "average_generation_time": 0.0,
                "success_rate": 0.0,
                "average_quality_score": 0.0,
                "latency_metrics": {
                    "topic_extraction_time_ms": {"average_ms": 0.0, "samples": 0},
                    "retrieval_time_ms": {"average_ms": 0.0, "samples": 0},
                    "generation_time_ms": {"average_ms": 0.0, "samples": 0},
                    "validation_time_ms": {"average_ms": 0.0, "samples": 0},
                    "analysis_time_ms": {"average_ms": 0.0, "samples": 0},
                },
            }

    async def search_by_topics(
        self, topics: List[str], limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search generations by topics.

        Args:
            topics: List of topics to search for
            limit: Maximum results to return

        Returns:
            List of matching generations
        """
        try:

            def _op() -> List[Dict[str, Any]]:
                with self._connection() as conn:
                    cursor = conn.cursor()

                    conditions = " OR ".join(["topics LIKE ?" for _ in topics])
                    search_params: List[Any] = [f"%{topic}%" for topic in topics]
                    search_params.append(limit)
                    query = (
                        "SELECT timestamp, topics, hypothetical, quality_score "
                        "FROM generation_history "
                        "WHERE " + conditions + " "
                        "ORDER BY timestamp DESC "
                        "LIMIT ?"
                    )
                    cursor.execute(query, search_params)
                    rows = cursor.fetchall()

                results = []
                for row in rows:
                    results.append(
                        {
                            "timestamp": row["timestamp"],
                            "topics": self._safe_json_decode(
                                row["topics"], field_name="topics", fallback=[]
                            ),
                            "hypothetical": row["hypothetical"][:200] + "...",
                            "quality_score": row["quality_score"],
                        }
                    )
                return results

            results = await self._run_in_thread(_op)

            logger.info("Search completed", topics=topics, results=len(results))
            return results

        except Exception as e:
            logger.error("Search failed", error=str(e))
            return []

    async def enforce_retention(
        self, max_generations: int, max_reports: int
    ) -> Dict[str, int]:
        """Trim old generations/reports to configured retention caps."""
        try:
            normalized_generations = max(1, int(max_generations))
            normalized_reports = max(1, int(max_reports))
        except (TypeError, ValueError):
            raise ValueError("Retention limits must be positive integers")

        def _op() -> Dict[str, int]:
            with self._connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT id
                    FROM generation_history
                    ORDER BY timestamp DESC
                    LIMIT -1 OFFSET ?
                    """,
                    (normalized_generations,),
                )
                generation_rows = cursor.fetchall()
                generation_ids = [int(row["id"]) for row in generation_rows]
                if generation_ids:
                    cursor.executemany(
                        "DELETE FROM generation_history WHERE id = ?",
                        [(generation_id,) for generation_id in generation_ids],
                    )

                cursor.execute(
                    """
                    SELECT id
                    FROM generation_reports
                    ORDER BY created_at DESC
                    LIMIT -1 OFFSET ?
                    """,
                    (normalized_reports,),
                )
                report_rows = cursor.fetchall()
                report_ids = [int(row["id"]) for row in report_rows]
                if report_ids:
                    cursor.executemany(
                        "DELETE FROM generation_reports WHERE id = ?",
                        [(report_id,) for report_id in report_ids],
                    )

                conn.commit()
            return {
                "deleted_generations": len(generation_ids),
                "deleted_reports": len(report_ids),
            }

        deleted = await self._run_in_thread(_op)
        logger.info("Retention cleanup completed", **deleted)
        return deleted

    async def health_check(self) -> Dict[str, Any]:
        """Check database health."""
        health_status = {
            "database_exists": self._db_path.exists(),
            "database_path": str(self._db_path),
            "connection_ok": False,
            "record_count": 0,
        }

        try:

            def _op() -> int:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM generation_history")
                    count = cursor.fetchone()[0]
                    return int(count)

            health_status["record_count"] = await self._run_in_thread(_op)
            health_status["connection_ok"] = True

        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            health_status["error"] = str(e)

        return health_status

    async def export_approved_training_data(
        self, output_path: str, min_score: float = 7.0
    ) -> int:
        """Export high-quality generations as ML training data CSV."""

        def _export():
            import csv as _csv

            rows = []
            with self._connection() as conn:
                cursor = conn.execute(
                    "SELECT id, topics, hypothetical, quality_score, request_data FROM generation_history "
                    "WHERE validation_passed = 1 AND quality_score >= ?",
                    (min_score,),
                )
                for row in cursor.fetchall():
                    text = row["hypothetical"] or ""
                    if not text.strip():
                        continue
                    req = self._decode_json_payload(
                        row["request_data"], field_name="request_data", fallback={}
                    )
                    topics = req.get("topics", [])
                    complexity = req.get("complexity_level", "intermediate")
                    complexity_map = {
                        "beginner": 1,
                        "basic": 2,
                        "intermediate": 3,
                        "advanced": 4,
                        "expert": 5,
                    }
                    comp_int = (
                        complexity_map.get(str(complexity).lower(), 3)
                        if not isinstance(complexity, int)
                        else complexity
                    )
                    rows.append(
                        {
                            "id": str(row["id"]),
                            "text": text,
                            "topics": (
                                "|".join(topics)
                                if isinstance(topics, list)
                                else str(topics)
                            ),
                            "complexity": comp_int,
                            "quality_score": round(
                                float(row["quality_score"] or 0.7), 2
                            ),
                        }
                    )
            if not rows:
                return 0
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", encoding="utf-8", newline="") as f:
                writer = _csv.DictWriter(
                    f,
                    fieldnames=["id", "text", "topics", "complexity", "quality_score"],
                )
                writer.writeheader()
                writer.writerows(rows)
            return len(rows)

        return await self._run_in_thread(_export)


# Global database service instance
database_service = DatabaseService()
