"""
AP Job Posting Lead Generation System — Main Orchestrator

This is the entry point that coordinates:
1. Running all scraper tiers (SerpAPI → JSearch → Playwright)
2. Normalizing and deduplicating results
3. Filtering to US-only jobs
4. Writing new entries to Google Sheets

Run directly:  python main.py
Run with args:  python main.py --tier 1 --keyword "Accounts Payable"
"""

import argparse
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    AP_KEYWORDS,
    US_LOCATIONS,
    NICHE_BOARDS,
    SQLITE_DB_PATH,
)
from scrapers.serpapi_google_jobs import search_google_jobs
from scrapers.rapidapi_jsearch import search_jsearch_jobs
from scrapers.playwright_scraper import run_niche_scraping
from processing.normalizer import normalize_jobs
from processing.deduplicator import Deduplicator
from processing.us_filter import filter_us_jobs
from storage.database import DatabaseManager
from storage.google_sheets import GoogleSheetsWriter

# ─── Logging Setup ──────────────────────────────────────────
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

log_filename = os.path.join(LOG_DIR, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_filename, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("main")


def run_tier1(keywords: list[str], locations: list[str]) -> list[dict]:
    """
    Tier 1: SerpAPI Google Jobs — primary data source.
    Searches each keyword × location combination.
    """
    all_jobs = []

    for keyword in keywords:
        for location in locations:
            try:
                jobs = search_google_jobs(keyword, location)
                all_jobs.extend(jobs)
                logger.info(f"Tier 1: {len(jobs)} jobs for '{keyword}' in '{location}'")
            except Exception as e:
                logger.error(f"Tier 1 error: '{keyword}' in '{location}': {e}")

    logger.info(f"Tier 1 total (before dedup): {len(all_jobs)} jobs")
    return all_jobs


def run_tier2(keywords: list[str], locations: list[str]) -> list[dict]:
    """
    Tier 2: RapidAPI JSearch — supplementary data source.
    Uses a smaller subset of locations to avoid burning free tier quota.
    """
    all_jobs = []

    # Use fewer locations for Tier 2 to conserve API quota
    tier2_locations = locations[:5] if len(locations) > 5 else locations

    for keyword in keywords:
        for location in tier2_locations:
            try:
                jobs = search_jsearch_jobs(keyword, location)
                all_jobs.extend(jobs)
                logger.info(f"Tier 2: {len(jobs)} jobs for '{keyword}' in '{location}'")
            except Exception as e:
                logger.error(f"Tier 2 error: '{keyword}' in '{location}': {e}")

    logger.info(f"Tier 2 total (before dedup): {len(all_jobs)} jobs")
    return all_jobs


def run_tier3(keywords: list[str]) -> list[dict]:
    """
    Tier 3: Playwright direct scraping — niche boards.
    """
    all_jobs = []

    for keyword in keywords:
        try:
            jobs = run_niche_scraping(keyword, NICHE_BOARDS)
            all_jobs.extend(jobs)
            logger.info(f"Tier 3: {len(jobs)} jobs for '{keyword}'")
        except Exception as e:
            logger.error(f"Tier 3 error for '{keyword}': {e}")

    logger.info(f"Tier 3 total (before dedup): {len(all_jobs)} jobs")
    return all_jobs


def run_pipeline(
    tiers: list[int] = None,
    keywords: list[str] = None,
    locations: list[str] = None,
    dry_run: bool = False,
):
    """
    Execute the full scraping pipeline.

    Args:
        tiers: Which tiers to run (default: all [1, 2, 3])
        keywords: Override default keywords
        locations: Override default locations
        dry_run: If True, don't write to Google Sheets (just log what would be written)
    """
    if tiers is None:
        tiers = [1, 2, 3]
    if keywords is None:
        keywords = AP_KEYWORDS
    if locations is None:
        locations = US_LOCATIONS

    start_time = datetime.now()
    logger.info("=" * 70)
    logger.info(f"AP Lead Gen Pipeline Started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Tiers: {tiers} | Keywords: {len(keywords)} | Locations: {len(locations)}")
    logger.info("=" * 70)

    # ── Step 1: Collect raw jobs from all tiers ──
    raw_jobs = []

    if 1 in tiers:
        logger.info("─── Running Tier 1: SerpAPI Google Jobs ───")
        raw_jobs.extend(run_tier1(keywords, locations))

    if 2 in tiers:
        logger.info("─── Running Tier 2: RapidAPI JSearch ───")
        raw_jobs.extend(run_tier2(keywords, locations))

    if 3 in tiers:
        logger.info("─── Running Tier 3: Playwright Niche Boards ───")
        raw_jobs.extend(run_tier3(keywords))

    logger.info(f"\nTotal raw jobs collected: {len(raw_jobs)}")

    if not raw_jobs:
        logger.warning("No jobs collected. Check API keys and network connectivity.")
        return

    # ── Step 2: Normalize ──
    logger.info("─── Normalizing data ───")
    normalized = normalize_jobs(raw_jobs)
    logger.info(f"Normalized: {len(normalized)} jobs")

    # ── Step 3: Filter US-only ──
    logger.info("─── Filtering US-only jobs ───")
    us_jobs = filter_us_jobs(normalized)
    logger.info(f"US jobs: {len(us_jobs)}")

    # ── Step 4: Deduplicate ──
    logger.info("─── Deduplicating ───")
    db = DatabaseManager(SQLITE_DB_PATH)
    deduper = Deduplicator(db)
    new_jobs = deduper.filter_new_jobs(us_jobs)
    logger.info(f"New unique jobs: {len(new_jobs)} (filtered {len(us_jobs) - len(new_jobs)} duplicates)")

    if not new_jobs:
        logger.info("No new jobs to write. All collected jobs were duplicates.")
        db.close()
        return

    # ── Step 5: Write to Google Sheets ──
    if dry_run:
        logger.info(f"DRY RUN: Would write {len(new_jobs)} jobs to Google Sheets")
        for job in new_jobs[:5]:
            logger.info(f"  → {job.get('company_name')} | {job.get('job_title')} | {job.get('source')}")
        if len(new_jobs) > 5:
            logger.info(f"  ... and {len(new_jobs) - 5} more")
    else:
        logger.info("─── Writing to Google Sheets ───")
        sheets = GoogleSheetsWriter()

        if sheets.initialize():
            written = sheets.write_jobs(new_jobs)
            logger.info(f"Successfully wrote {written} rows to Google Sheets")

            # Mark as seen in dedup DB ONLY after successful write
            if written > 0:
                deduper.mark_as_seen(new_jobs)
                logger.info(f"Marked {len(new_jobs)} jobs as seen in dedup DB")
            else:
                logger.warning("No rows written to Sheets — jobs NOT marked as seen (will retry next run)")
        else:
            logger.error("Failed to initialize Google Sheets. Jobs not written!")
            logger.info("Tip: Run with --dry-run to test without Google Sheets")

    # ── Summary ──
    elapsed = (datetime.now() - start_time).total_seconds()
    stats = deduper.get_stats()
    db.close()

    logger.info("\n" + "=" * 70)
    logger.info("PIPELINE SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Duration: {elapsed:.1f} seconds")
    logger.info(f"Raw jobs collected: {len(raw_jobs)}")
    logger.info(f"After normalization: {len(normalized)}")
    logger.info(f"After US filter: {len(us_jobs)}")
    logger.info(f"After dedup: {len(new_jobs)} new jobs")
    logger.info(f"Total jobs in DB: {stats.get('total_seen', 'N/A')}")
    logger.info(f"Unique companies in DB: {stats.get('unique_companies', 'N/A')}")
    logger.info(f"Jobs by source: {stats.get('by_source', {})}")
    logger.info("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="AP Job Posting Lead Generation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                              # Run full pipeline (all tiers)
  python main.py --dry-run                    # Test without writing to Sheets
  python main.py --tier 1                     # Run only SerpAPI (Tier 1)
  python main.py --tier 1 2                   # Run Tier 1 and 2
  python main.py --keyword "Accounts Payable" # Single keyword
  python main.py --tier 1 --dry-run           # Test Tier 1 only
        """,
    )

    parser.add_argument(
        "--tier",
        type=int,
        nargs="+",
        choices=[1, 2, 3],
        default=[1, 2, 3],
        help="Which scraping tiers to run (1=SerpAPI, 2=JSearch, 3=Playwright)",
    )

    parser.add_argument(
        "--keyword",
        type=str,
        nargs="+",
        default=None,
        help="Override default keywords (e.g., --keyword 'Accounts Payable')",
    )

    parser.add_argument(
        "--location",
        type=str,
        nargs="+",
        default=None,
        help="Override default locations (e.g., --location 'New York, NY')",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without writing to Google Sheets (test mode)",
    )

    args = parser.parse_args()

    run_pipeline(
        tiers=args.tier,
        keywords=args.keyword,
        locations=args.location,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
