"""
Deduplicator — prevents the same job from being added twice.

Uses SQLite to maintain a persistent registry of seen job URLs and
company+title hashes. Checks both exact URL matches and fuzzy
company+title matches to catch cross-source duplicates.
"""

import logging
import hashlib
from storage.sqlite_db import SQLiteDB

logger = logging.getLogger(__name__)


class Deduplicator:
    """
    Deduplicates jobs using a SQLite-backed registry.
    Two dedup strategies:
      1. Exact URL match
      2. Company+Title content hash (catches same job posted on different boards)
    """

    def __init__(self, db: SQLiteDB):
        self.db = db

    def filter_new_jobs(self, jobs: list[dict]) -> list[dict]:
        """
        Filter a list of jobs, returning only those not seen before.

        Args:
            jobs: List of normalized job dicts.

        Returns:
            List of jobs that are new (not in the dedup registry).
        """
        new_jobs = []
        seen_in_batch = set()  # Catch within-batch duplicates too

        for job in jobs:
            url = job.get("job_url", "")
            content_hash = self._make_content_hash(job)

            # Skip if we've seen this in the current batch
            batch_key = url or content_hash
            if batch_key in seen_in_batch:
                continue

            # Check against persistent DB
            if url and self.db.url_exists(url):
                logger.debug(f"Duplicate (URL): {url}")
                continue

            if content_hash and self.db.hash_exists(content_hash):
                logger.debug(f"Duplicate (content): {job.get('company_name')} - {job.get('job_title')}")
                continue

            # It's new!
            new_jobs.append(job)
            seen_in_batch.add(batch_key)

        return new_jobs

    def mark_as_seen(self, jobs: list[dict]):
        """
        Mark a list of jobs as seen in the dedup registry.
        Call this AFTER successfully writing to Google Sheets.

        Args:
            jobs: List of job dicts to mark as seen.
        """
        for job in jobs:
            url = job.get("job_url", "")
            content_hash = self._make_content_hash(job)
            source = job.get("source", "")
            company = job.get("company_name", "")
            title = job.get("job_title", "")

            self.db.insert_seen_job(
                url=url,
                content_hash=content_hash,
                source=source,
                company=company,
                title=title,
            )

    def get_stats(self) -> dict:
        """Get dedup database statistics."""
        return self.db.get_stats()

    @staticmethod
    def _make_content_hash(job: dict) -> str:
        """
        Create a content hash from company name + job title.
        This catches the same job posted on different boards.
        """
        company = (job.get("company_name", "") or "").lower().strip()
        title = (job.get("job_title", "") or "").lower().strip()

        if not company or not title:
            return ""

        # Normalize common variations
        company = company.replace(",", "").replace(".", "").replace("inc", "").replace("llc", "")
        title = title.replace(",", "").replace(".", "")

        content = f"{company}|{title}"
        return hashlib.md5(content.encode()).hexdigest()
