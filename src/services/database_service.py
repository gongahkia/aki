"""
Database Service for persisting generation history using SQLite.
Lightweight, local-only storage perfect for internal tools.
"""

import asyncio
import sqlite3
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class DatabaseService:
    """Service for managing SQLite database for generation history."""

    def __init__(self, db_path: str = None):
        from ..config import settings as app_settings
        self._db_path = Path(db_path or app_settings.database_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.Connection(str(self._db_path))
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        return conn

    def _initialize_database(self):
        """Initialize database schema."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Create generation_history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS generation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    topics TEXT NOT NULL,
                    law_domain TEXT,
                    number_parties INTEGER,
                    complexity_level TEXT,
                    hypothetical TEXT,
                    analysis TEXT,
                    generation_time REAL,
                    validation_passed BOOLEAN,
                    quality_score REAL,
                    request_data TEXT,
                    response_data TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index on timestamp for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON generation_history(timestamp DESC)
            """)

            # Create index on topics for searching
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_topics
                ON generation_history(topics)
            """)

            conn.commit()
            conn.close()

            logger.info("Database initialized", db_path=str(self._db_path))

        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            raise

    async def save_generation(
        self,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any]
    ) -> int:
        """
        Save a generation to the database.

        Returns:
            The ID of the inserted record
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Extract key fields for indexing/searching
            cursor.execute("""
                INSERT INTO generation_history (
                    timestamp, topics, law_domain, number_parties, complexity_level,
                    hypothetical, analysis, generation_time, validation_passed,
                    quality_score, request_data, response_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                response_data.get('metadata', {}).get('generation_timestamp', datetime.utcnow().isoformat()),
                json.dumps(request_data.get('topics', [])),
                request_data.get('law_domain'),
                request_data.get('number_parties'),
                request_data.get('complexity_level'),
                response_data.get('hypothetical', ''),
                response_data.get('analysis', ''),
                response_data.get('generation_time', 0.0),
                response_data.get('validation_results', {}).get('passed', False),
                response_data.get('validation_results', {}).get('quality_score', 0.0),
                json.dumps(request_data),
                json.dumps(response_data)
            ))

            record_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info("Generation saved to database", id=record_id)
            return record_id

        except Exception as e:
            logger.error("Failed to save generation", error=str(e))
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
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    timestamp, request_data, response_data
                FROM generation_history
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))

            rows = cursor.fetchall()
            conn.close()

            # Convert to list of dicts
            generations = []
            for row in rows:
                generations.append({
                    'timestamp': row['timestamp'],
                    'request': json.loads(row['request_data']),
                    'response': json.loads(row['response_data'])
                })

            logger.info("Retrieved recent generations", count=len(generations))
            return generations

        except Exception as e:
            logger.error("Failed to get recent generations", error=str(e))
            return []

    async def get_statistics(self) -> Dict[str, Any]:
        """
        Get generation statistics from database.

        Returns:
            Dict with statistics (total, avg_time, success_rate, etc.)
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get overall statistics
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

            # Get topic distribution
            cursor.execute("""
                SELECT
                    topics, COUNT(*) as count
                FROM generation_history
                GROUP BY topics
                ORDER BY count DESC
                LIMIT 10
            """)

            topic_rows = cursor.fetchall()
            conn.close()

            stats = {
                'total_generations': row['total_generations'] or 0,
                'average_generation_time': row['avg_generation_time'] or 0.0,
                'success_rate': (row['success_rate'] or 0.0) * 100,  # Convert to percentage
                'average_quality_score': row['avg_quality_score'] or 0.0,
                'first_generation': row['first_generation'],
                'last_generation': row['last_generation'],
                'popular_topics': [
                    {'topics': json.loads(t['topics']), 'count': t['count']}
                    for t in topic_rows
                ]
            }

            logger.info("Retrieved statistics", total=stats['total_generations'])
            return stats

        except Exception as e:
            logger.error("Failed to get statistics", error=str(e))
            return {
                'total_generations': 0,
                'average_generation_time': 0.0,
                'success_rate': 0.0,
                'average_quality_score': 0.0
            }

    async def search_by_topics(self, topics: List[str], limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search generations by topics.

        Args:
            topics: List of topics to search for
            limit: Maximum results to return

        Returns:
            List of matching generations
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # build parameterized query
            conditions = " OR ".join(["topics LIKE ?" for _ in topics])
            search_params = [f'%{topic}%' for topic in topics]
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
            conn.close()

            results = []
            for row in rows:
                results.append({
                    'timestamp': row['timestamp'],
                    'topics': json.loads(row['topics']),
                    'hypothetical': row['hypothetical'][:200] + '...',  # Preview
                    'quality_score': row['quality_score']
                })

            logger.info("Search completed", topics=topics, results=len(results))
            return results

        except Exception as e:
            logger.error("Search failed", error=str(e))
            return []

    async def health_check(self) -> Dict[str, Any]:
        """Check database health."""
        health_status = {
            'database_exists': self._db_path.exists(),
            'database_path': str(self._db_path),
            'connection_ok': False,
            'record_count': 0
        }

        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM generation_history")
            health_status['record_count'] = cursor.fetchone()[0]
            health_status['connection_ok'] = True
            conn.close()

        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            health_status['error'] = str(e)

        return health_status


# Global database service instance
database_service = DatabaseService()
