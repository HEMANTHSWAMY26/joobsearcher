"""
Data Normalizer — converts raw job data from different scrapers
into a consistent schema for deduplication and storage.
"""

import logging
import re
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def normalize_job(job: dict) -> dict:
    """
    Normalize a job dict to ensure consistent field formats.

    Args:
        job: Raw job dict from any scraper.

    Returns:
        Normalized job dict with cleaned fields.
    """
    normalized = {}

    # Clean text fields
    normalized["company_name"] = _clean_text(job.get("company_name", ""))
    normalized["job_title"] = _clean_text(job.get("job_title", ""))
    normalized["job_description"] = _clean_description(job.get("job_description", ""))
    normalized["job_location"] = _clean_text(job.get("job_location", ""))
    normalized["city"] = _clean_text(job.get("city", ""))
    normalized["state"] = _normalize_state(job.get("state", ""))
    normalized["country"] = _normalize_country(job.get("country", ""))
    normalized["employment_type"] = _normalize_employment_type(job.get("employment_type", ""))
    normalized["experience_level"] = _clean_text(job.get("experience_level", ""))
    normalized["posted_date"] = _normalize_date(job.get("posted_date", ""))
    normalized["job_url"] = (job.get("job_url", "") or "").strip()
    normalized["source"] = _clean_text(job.get("source", ""))
    normalized["company_size"] = _clean_text(job.get("company_size", ""))
    normalized["industry"] = _clean_text(job.get("industry", ""))

    # Metadata
    normalized["job_id"] = job.get("job_id", "")
    normalized["search_keyword"] = job.get("search_keyword", "")
    normalized["scraped_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return normalized


def normalize_jobs(jobs: list[dict]) -> list[dict]:
    """Normalize a list of jobs."""
    normalized = []
    for job in jobs:
        try:
            n = normalize_job(job)
            if n["company_name"] and n["job_title"]:
                normalized.append(n)
            else:
                logger.debug(f"Skipping job with missing company/title: {job}")
        except Exception as e:
            logger.error(f"Error normalizing job: {e}")
    return normalized


def _clean_text(text: str) -> str:
    """Clean whitespace, newlines, and special characters from text."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', str(text)).strip()
    # Remove non-printable characters
    text = ''.join(c for c in text if c.isprintable())
    return text[:500]  # Cap length


def _clean_description(text: str) -> str:
    """Clean job description text, keeping more content."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', str(text)).strip()
    text = ''.join(c for c in text if c.isprintable())
    return text[:5000]  # Allow longer descriptions


def _normalize_state(state: str) -> str:
    """Normalize US state to 2-letter code."""
    if not state:
        return ""

    state = state.strip()

    # Already a 2-letter code
    if len(state) == 2 and state.upper().isalpha():
        return state.upper()

    # Full state name to abbreviation
    state_map = {
        "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
        "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
        "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
        "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
        "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
        "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
        "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
        "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
        "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
        "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
        "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
        "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
        "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
    }

    return state_map.get(state.lower(), state[:20])


def _normalize_country(country: str) -> str:
    """Normalize country to standard form."""
    if not country:
        return "US"
    country = country.strip().upper()
    us_variants = {"US", "USA", "UNITED STATES", "UNITED STATES OF AMERICA", "U.S.", "U.S.A."}
    if country in us_variants:
        return "US"
    return country[:20]


def _normalize_employment_type(emp_type: str) -> str:
    """Normalize employment type to consistent format."""
    if not emp_type:
        return ""

    emp_lower = emp_type.lower().strip()

    if "full" in emp_lower:
        return "Full-time"
    elif "part" in emp_lower:
        return "Part-time"
    elif "contract" in emp_lower or "contractor" in emp_lower:
        return "Contract"
    elif "temp" in emp_lower:
        return "Temporary"
    elif "intern" in emp_lower:
        return "Internship"

    return emp_type.strip()[:50]


def _normalize_date(date_str: str) -> str:
    """
    Normalize date strings to YYYY-MM-DD format.
    Handles relative dates like '3 days ago', 'just posted', etc.
    """
    if not date_str:
        return ""

    date_str = date_str.strip()

    # Already in ISO format
    if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
        return date_str[:10]

    # Relative date parsing
    date_lower = date_str.lower()
    now = datetime.now()

    if "just" in date_lower or "today" in date_lower or "now" in date_lower:
        return now.strftime("%Y-%m-%d")

    if "yesterday" in date_lower:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")

    # "X days ago", "X hours ago"
    match = re.search(r'(\d+)\s*(day|hour|minute|week|month)', date_lower)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)

        if unit == "hour" or unit == "minute":
            return now.strftime("%Y-%m-%d")
        elif unit == "day":
            return (now - timedelta(days=amount)).strftime("%Y-%m-%d")
        elif unit == "week":
            return (now - timedelta(weeks=amount)).strftime("%Y-%m-%d")
        elif unit == "month":
            return (now - timedelta(days=amount * 30)).strftime("%Y-%m-%d")

    return date_str[:20]
