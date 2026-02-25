"""
Database abstraction layer — supports both SQLite (local) and PostgreSQL/Neon (cloud).

Automatically uses PostgreSQL when DATABASE_URL is set (Neon/Render),
falls back to SQLite for local development.
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Check for PostgreSQL support
try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

DATABASE_URL = os.getenv("DATABASE_URL", "")


class DatabaseManager:
    """
    Unified database interface that works with both SQLite and PostgreSQL.
    Uses PostgreSQL when DATABASE_URL is set, otherwise SQLite.
    """

    def __init__(self, sqlite_path: str = "data/jobs_dedup.db"):
        self.use_postgres = bool(DATABASE_URL) and POSTGRES_AVAILABLE
        self.sqlite_path = sqlite_path
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        if self.use_postgres:
            logger.info(f"Using PostgreSQL (Neon): {DATABASE_URL[:40]}...")
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_jobs (
                    id SERIAL PRIMARY KEY,
                    url TEXT,
                    content_hash TEXT,
                    source TEXT,
                    company TEXT,
                    title TEXT,
                    seen_at TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_url ON seen_jobs(url)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash ON seen_jobs(content_hash)")
            conn.commit()
            conn.close()
        else:
            logger.info(f"Using SQLite: {self.sqlite_path}")
            os.makedirs(os.path.dirname(self.sqlite_path) or ".", exist_ok=True)
            conn = self._get_connection()
            cursor = conn.cursor()
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
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_url ON seen_jobs(url)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hash ON seen_jobs(content_hash)")
            conn.commit()
            conn.close()

    def _get_connection(self):
        """Get a database connection."""
        if self.use_postgres:
            conn = psycopg2.connect(DATABASE_URL, sslmode="require")
            return conn
        else:
            conn = sqlite3.connect(self.sqlite_path)
            conn.row_factory = sqlite3.Row
            return conn

    def url_exists(self, url: str) -> bool:
        if not url:
            return False
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM seen_jobs WHERE url = %s LIMIT 1" if self.use_postgres
                       else "SELECT 1 FROM seen_jobs WHERE url = ? LIMIT 1", (url,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def hash_exists(self, content_hash: str) -> bool:
        if not content_hash:
            return False
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM seen_jobs WHERE content_hash = %s LIMIT 1" if self.use_postgres
                       else "SELECT 1 FROM seen_jobs WHERE content_hash = ? LIMIT 1", (content_hash,))
        result = cursor.fetchone()
        conn.close()
        return result is not None

    def insert_seen_job(self, url: str, content_hash: str, source: str, company: str, title: str):
        conn = self._get_connection()
        cursor = conn.cursor()
        ph = "%s" if self.use_postgres else "?"
        cursor.execute(
            f"INSERT INTO seen_jobs (url, content_hash, source, company, title, seen_at) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (url, content_hash, source, company, title, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

    def get_stats(self) -> dict:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM seen_jobs")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT source) FROM seen_jobs")
        sources = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT company) FROM seen_jobs")
        companies = cursor.fetchone()[0]

        cursor.execute("SELECT source, COUNT(*) FROM seen_jobs GROUP BY source ORDER BY COUNT(*) DESC")
        by_source = {row[0]: row[1] for row in cursor.fetchall()}

        conn.close()
        return {
            "total_seen": total,
            "unique_sources": sources,
            "unique_companies": companies,
            "by_source": by_source,
        }

    def query_jobs(self, search: str = "", source: str = "", page: int = 1, per_page: int = 50) -> dict:
        """Query jobs with pagination, search, and source filter."""
        conn = self._get_connection()
        cursor = conn.cursor()
        offset = (page - 1) * per_page
        ph = "%s" if self.use_postgres else "?"

        conditions = []
        params = []

        if search:
            like = f"%{search}%"
            conditions.append(f"(company LIKE {ph} OR title LIKE {ph})")
            params.extend([like, like])

        if source:
            conditions.append(f"source = {ph}")
            params.append(source)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        cursor.execute(f"SELECT COUNT(*) FROM seen_jobs {where}", params)
        total = cursor.fetchone()[0]

        cursor.execute(
            f"SELECT id, url, content_hash, source, company, title, seen_at "
            f"FROM seen_jobs {where} ORDER BY seen_at DESC LIMIT {ph} OFFSET {ph}",
            params + [per_page, offset],
        )
        jobs = []
        for row in cursor.fetchall():
            if self.use_postgres:
                jobs.append({
                    "id": row[0], "url": row[1], "content_hash": row[2],
                    "source": row[3], "company": row[4], "title": row[5], "seen_at": row[6],
                })
            else:
                jobs.append(dict(row))

        conn.close()
        return {
            "jobs": jobs, "total": total, "page": page,
            "per_page": per_page, "pages": (total + per_page - 1) // per_page,
        }

    def get_sources(self) -> list:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT source FROM seen_jobs ORDER BY source")
        sources = [row[0] for row in cursor.fetchall()]
        conn.close()
        return sources

    def get_daily_counts(self, limit: int = 30) -> list:
        conn = self._get_connection()
        cursor = conn.cursor()
        if self.use_postgres:
            cursor.execute("""
                SELECT DATE(seen_at::timestamp) as day, COUNT(*) as count
                FROM seen_jobs GROUP BY DATE(seen_at::timestamp) ORDER BY day DESC LIMIT %s
            """, (limit,))
        else:
            cursor.execute("""
                SELECT DATE(seen_at) as day, COUNT(*) as count
                FROM seen_jobs GROUP BY DATE(seen_at) ORDER BY day DESC LIMIT ?
            """, (limit,))
        days = [{"date": str(row[0]), "count": row[1]} for row in cursor.fetchall()]
        conn.close()
        return days

    def close(self):
        pass  # Connections are per-operation, no persistent connection to close
