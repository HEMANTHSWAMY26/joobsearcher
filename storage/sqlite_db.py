"""
SQLite Database — persistent dedup registry and local data store.

Maintains a record of all job URLs and content hashes we've seen
to prevent duplicates across runs.
"""

import sqlite3
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)


class SQLiteDB:
    """Persistent SQLite database for job deduplication."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_directory()
        self.conn = sqlite3.connect(db_path)
        self._create_tables()

    def _ensure_directory(self):
        """Create the directory for the DB file if it doesn't exist."""
        directory = os.path.dirname(self.db_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def _create_tables(self):
        """Create the dedup tables if they don't exist."""
        cursor = self.conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seen_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT,
                content_hash TEXT,
                source TEXT,
                company TEXT,
                title TEXT,
                seen_at TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_url ON seen_jobs(url)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_hash ON seen_jobs(content_hash)
        """)

        self.conn.commit()
        logger.info(f"SQLite DB initialized at {self.db_path}")

    def url_exists(self, url: str) -> bool:
        """Check if a job URL has been seen before."""
        if not url:
            return False
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM seen_jobs WHERE url = ? LIMIT 1", (url,))
        return cursor.fetchone() is not None

    def hash_exists(self, content_hash: str) -> bool:
        """Check if a content hash has been seen before."""
        if not content_hash:
            return False
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM seen_jobs WHERE content_hash = ? LIMIT 1", (content_hash,))
        return cursor.fetchone() is not None

    def insert_seen_job(self, url: str, content_hash: str, source: str, company: str, title: str):
        """Mark a job as seen."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO seen_jobs (url, content_hash, source, company, title, seen_at) VALUES (?, ?, ?, ?, ?, ?)",
            (url, content_hash, source, company, title, datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_stats(self) -> dict:
        """Get database statistics."""
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM seen_jobs")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT source) FROM seen_jobs")
        sources = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT company) FROM seen_jobs")
        companies = cursor.fetchone()[0]

        cursor.execute("SELECT source, COUNT(*) FROM seen_jobs GROUP BY source ORDER BY COUNT(*) DESC")
        by_source = dict(cursor.fetchall())

        return {
            "total_seen": total,
            "unique_sources": sources,
            "unique_companies": companies,
            "by_source": by_source,
        }

    def close(self):
        """Close the database connection."""
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
