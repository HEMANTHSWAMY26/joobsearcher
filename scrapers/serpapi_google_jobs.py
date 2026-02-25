"""
Tier 1 — SerpAPI Google Jobs Scraper (Primary Data Source)

Google Jobs aggregates from Indeed, LinkedIn, Monster, Glassdoor, ZipRecruiter,
and company career sites. This is our most comprehensive single source.

Each search returns up to 10 results per page, with pagination support.
"""

import logging
import time
from typing import Optional
from serpapi import GoogleSearch

from config import SERPAPI_API_KEY, SERP_DATE_FILTER, SERP_MAX_PAGES

logger = logging.getLogger(__name__)


def search_google_jobs(keyword: str, location: str = "United States") -> list[dict]:
    """
    Search Google Jobs for a keyword + location combo.
    Returns a list of raw job dicts from SerpAPI.

    Args:
        keyword: Job search keyword (e.g., "Accounts Payable Clerk")
        location: Location string (e.g., "New York, NY" or "United States")

    Returns:
        List of job posting dicts with raw SerpAPI data.
    """
    all_jobs = []

    if not SERPAPI_API_KEY:
        logger.error("SERPAPI_API_KEY is not set. Skipping SerpAPI searches.")
        return all_jobs

    params = {
        "engine": "google_jobs",
        "q": keyword,
        "location": location,
        "hl": "en",
        "gl": "us",
        "chips": SERP_DATE_FILTER,
        "api_key": SERPAPI_API_KEY,
    }

    for page in range(SERP_MAX_PAGES):
        if page > 0:
            params["start"] = page * 10

        try:
            logger.info(f"SerpAPI search: '{keyword}' in '{location}' (page {page + 1})")
            search = GoogleSearch(params)
            results = search.get_dict()

            jobs = results.get("jobs_results", [])
            if not jobs:
                logger.info(f"No more results at page {page + 1}. Stopping pagination.")
                break

            for job in jobs:
                parsed = _parse_serpapi_job(job, keyword, location)
                if parsed:
                    all_jobs.append(parsed)

            logger.info(f"Found {len(jobs)} jobs on page {page + 1}")

            # Respect rate limits
            time.sleep(1.5)

        except Exception as e:
            logger.error(f"SerpAPI error for '{keyword}' in '{location}' page {page + 1}: {e}")
            break

    return all_jobs


def get_job_details(job_id: str) -> Optional[dict]:
    """
    Fetch detailed job description using SerpAPI's Google Jobs Listing endpoint.
    This gets the full description when the search result only has a snippet.

    Args:
        job_id: The job_id from a Google Jobs search result.

    Returns:
        Dict with full job details, or None if lookup fails.
    """
    if not SERPAPI_API_KEY:
        return None

    params = {
        "engine": "google_jobs_listing",
        "q": job_id,
        "api_key": SERPAPI_API_KEY,
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        return results
    except Exception as e:
        logger.error(f"SerpAPI job detail lookup failed for {job_id}: {e}")
        return None


def _parse_serpapi_job(job: dict, keyword: str, search_location: str) -> Optional[dict]:
    """
    Parse a single SerpAPI Google Jobs result into our common schema.

    Args:
        job: Raw job dict from SerpAPI.
        keyword: The keyword that found this job.
        search_location: The location used in the search.

    Returns:
        Normalized job dict, or None if data is insufficient.
    """
    try:
        title = job.get("title", "").strip()
        company = job.get("company_name", "").strip()

        if not title or not company:
            return None

        # Parse location
        location_raw = job.get("location", "")
        city, state, country = _parse_location(location_raw)

        # Parse detected extensions (employment type, etc.)
        extensions = job.get("detected_extensions", {})
        employment_type = extensions.get("schedule_type", "")
        posted_at = extensions.get("posted_at", "")

        # Get description (may be a snippet — full desc via detail API)
        description = job.get("description", "")

        # Build the job URL — Google Jobs doesn't give direct URLs,
        # but related_links contains the original posting URLs
        job_url = ""
        apply_links = job.get("apply_options", [])
        if apply_links:
            job_url = apply_links[0].get("link", "")

        # Determine the source from apply options
        source = "Google Jobs"
        if apply_links:
            source_name = apply_links[0].get("title", "")
            if source_name:
                source = source_name

        # Get the Google Jobs internal ID (useful for dedup & detail lookup)
        job_id = job.get("job_id", "")

        return {
            "company_name": company,
            "job_title": title,
            "job_description": description[:5000],  # Cap at 5000 chars for Sheets
            "job_location": location_raw,
            "city": city,
            "state": state,
            "country": country or "US",
            "employment_type": employment_type,
            "experience_level": _extract_experience_level(description),
            "posted_date": posted_at,
            "job_url": job_url,
            "source": source,
            "company_size": "",  # Enriched later via Tier 2
            "industry": "",  # Enriched later via Tier 2
            "job_id": job_id,
            "search_keyword": keyword,
        }
    except Exception as e:
        logger.error(f"Error parsing SerpAPI job: {e}")
        return None


def _parse_location(location_raw: str) -> tuple[str, str, str]:
    """
    Parse a location string like 'New York, NY' or 'Austin, TX, United States'
    into (city, state, country).
    """
    parts = [p.strip() for p in location_raw.split(",")]

    city = ""
    state = ""
    country = "US"

    if len(parts) >= 1:
        city = parts[0]
    if len(parts) >= 2:
        state = parts[1]
    if len(parts) >= 3:
        country = parts[2]

    return city, state, country


def _extract_experience_level(description: str) -> str:
    """
    Extract experience level from job description text using keyword matching.
    """
    desc_lower = description.lower()

    if any(kw in desc_lower for kw in ["entry level", "entry-level", "0-1 year", "no experience"]):
        return "Entry Level"
    elif any(kw in desc_lower for kw in ["senior", "sr.", "7+ years", "8+ years", "10+ years", "lead"]):
        return "Senior"
    elif any(kw in desc_lower for kw in ["mid-level", "mid level", "3-5 years", "3+ years", "4+ years", "5+ years"]):
        return "Mid Level"
    elif any(kw in desc_lower for kw in ["manager", "director", "vp ", "vice president"]):
        return "Manager/Director"
    elif any(kw in desc_lower for kw in ["junior", "jr.", "1-2 years", "1-3 years", "2+ years"]):
        return "Junior"

    return ""
