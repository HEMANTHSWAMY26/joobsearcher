"""
Tier 2 — RapidAPI JSearch Scraper (Supplementary Data Source)

JSearch aggregates jobs from Indeed, LinkedIn, Glassdoor, ZipRecruiter, and more.
Used to supplement SerpAPI data and enrich with company size/industry info.
"""

import logging
import time
from typing import Optional
import requests

from config import RAPIDAPI_KEY, JSEARCH_HOST, JSEARCH_DATE_POSTED, JSEARCH_MAX_PAGES

logger = logging.getLogger(__name__)

JSEARCH_URL = "https://jsearch.p.rapidapi.com/search"
JSEARCH_DETAILS_URL = "https://jsearch.p.rapidapi.com/job-details"


def search_jsearch_jobs(keyword: str, location: str = "United States") -> list[dict]:
    """
    Search JSearch API for AP job postings.

    Args:
        keyword: Job search keyword (e.g., "Accounts Payable Clerk")
        location: Location string (e.g., "New York, NY")

    Returns:
        List of normalized job dicts.
    """
    all_jobs = []

    if not RAPIDAPI_KEY:
        logger.warning("RAPIDAPI_KEY is not set. Skipping JSearch searches.")
        return all_jobs

    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": JSEARCH_HOST,
    }

    for page in range(1, JSEARCH_MAX_PAGES + 1):
        params = {
            "query": f"{keyword} in {location}",
            "page": str(page),
            "num_pages": "1",
            "date_posted": JSEARCH_DATE_POSTED,
            "country": "us",
            "language": "en",
        }

        try:
            logger.info(f"JSearch: '{keyword}' in '{location}' (page {page})")
            response = requests.get(JSEARCH_URL, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            jobs = data.get("data", [])

            if not jobs:
                logger.info(f"No more JSearch results at page {page}. Stopping.")
                break

            for job in jobs:
                parsed = _parse_jsearch_job(job, keyword)
                if parsed:
                    all_jobs.append(parsed)

            logger.info(f"Found {len(jobs)} jobs on page {page}")

            # Respect rate limits
            time.sleep(2)

        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 429:
                logger.warning("JSearch rate limit hit. Pausing for 60 seconds.")
                time.sleep(60)
            else:
                logger.error(f"JSearch HTTP error: {e}")
                break
        except Exception as e:
            logger.error(f"JSearch error for '{keyword}' page {page}: {e}")
            break

    return all_jobs


def _parse_jsearch_job(job: dict, keyword: str) -> Optional[dict]:
    """
    Parse a JSearch job result into our common schema.
    """
    try:
        title = (job.get("job_title") or "").strip()
        company = (job.get("employer_name") or "").strip()

        if not title or not company:
            return None

        city = (job.get("job_city") or "").strip()
        state = (job.get("job_state") or "").strip()
        country = (job.get("job_country") or "US").strip()

        location_parts = [p for p in [city, state, country] if p]
        location_str = ", ".join(location_parts)

        # Employment type
        employment_type = (job.get("job_employment_type") or "").strip()
        if employment_type:
            type_map = {
                "FULLTIME": "Full-time",
                "PARTTIME": "Part-time",
                "CONTRACTOR": "Contract",
                "INTERN": "Internship",
                "TEMPORARY": "Temporary",
            }
            employment_type = type_map.get(employment_type.upper(), employment_type)

        # Description
        description = (job.get("job_description") or "")[:5000]

        # Experience level from required experience
        experience = job.get("job_required_experience", {}) or {}
        exp_level = (experience.get("required_experience_in_months") or "")
        experience_level = _map_experience(exp_level, description)

        # Posted date
        posted_date = (job.get("job_posted_at_datetime_utc") or "")[:10]  # YYYY-MM-DD

        # Job URL
        job_url = job.get("job_apply_link") or job.get("job_google_link") or ""

        # Source
        source = (job.get("job_publisher") or "JSearch").strip()

        # Company details (JSearch often has these!)
        employer = job.get("employer_company_type") or ""
        company_size = ""
        num_employees = job.get("employer_company_type") or ""

        # Job ID for dedup
        job_id = job.get("job_id", "")

        return {
            "company_name": company,
            "job_title": title,
            "job_description": description,
            "job_location": location_str,
            "city": city,
            "state": state,
            "country": country if country else "US",
            "employment_type": employment_type,
            "experience_level": experience_level,
            "posted_date": posted_date,
            "job_url": job_url,
            "source": source,
            "company_size": company_size,
            "industry": employer,
            "job_id": job_id,
            "search_keyword": keyword,
        }
    except Exception as e:
        logger.error(f"Error parsing JSearch job: {e}")
        return None


def _map_experience(months_str: str, description: str) -> str:
    """Map experience months or description keywords to level."""
    if months_str:
        try:
            months = int(months_str)
            if months <= 12:
                return "Entry Level"
            elif months <= 36:
                return "Junior"
            elif months <= 60:
                return "Mid Level"
            elif months <= 96:
                return "Senior"
            else:
                return "Manager/Director"
        except (ValueError, TypeError):
            pass

    # Fallback to keyword matching
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in ["entry level", "entry-level", "0-1 year"]):
        return "Entry Level"
    elif any(kw in desc_lower for kw in ["senior", "sr.", "7+ years", "10+ years"]):
        return "Senior"
    elif any(kw in desc_lower for kw in ["mid-level", "3-5 years", "5+ years"]):
        return "Mid Level"
    elif any(kw in desc_lower for kw in ["manager", "director"]):
        return "Manager/Director"

    return ""
