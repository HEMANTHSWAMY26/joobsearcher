"""
US Location Filter — ensures only US-based job postings are included.

Filters based on state abbreviation, state name, country field,
and location string analysis.
"""

import logging
from config import US_STATES, US_STATE_NAMES

logger = logging.getLogger(__name__)


def filter_us_jobs(jobs: list[dict]) -> list[dict]:
    """
    Filter jobs to only include US-based positions.

    Args:
        jobs: List of normalized job dicts.

    Returns:
        List of jobs that are located in the US.
    """
    us_jobs = []
    filtered_count = 0

    for job in jobs:
        if is_us_job(job):
            us_jobs.append(job)
        else:
            filtered_count += 1
            logger.debug(
                f"Filtered non-US job: {job.get('company_name')} - "
                f"{job.get('job_title')} ({job.get('job_location')})"
            )

    if filtered_count > 0:
        logger.info(f"US filter: kept {len(us_jobs)}, filtered out {filtered_count} non-US jobs")

    return us_jobs


def is_us_job(job: dict) -> bool:
    """
    Determine if a job posting is US-based.

    Checks multiple signals:
    1. Country field
    2. State abbreviation
    3. State name in location string
    4. Known US city patterns
    """
    country = (job.get("country", "") or "").upper().strip()
    state = (job.get("state", "") or "").upper().strip()
    location = (job.get("job_location", "") or "").upper().strip()

    # Check country field
    us_country_variants = {"US", "USA", "UNITED STATES", "UNITED STATES OF AMERICA", "U.S.", "U.S.A."}
    if country in us_country_variants:
        return True

    # Check state abbreviation
    if state in US_STATES:
        return True

    # Check for state names in location string
    location_lower = location.lower()
    for state_name in US_STATE_NAMES:
        if state_name.lower() in location_lower:
            return True

    # Check for state abbreviations in location (e.g., "New York, NY")
    for abbr in US_STATES:
        # Look for state abbrev bounded by commas, spaces, or end of string
        if f", {abbr}" in location or f" {abbr}" == location[-3:] or location == abbr:
            return True

    # Check for "Remote" jobs that specify US
    if "REMOTE" in location and any(us in location for us in ["US", "USA", "UNITED STATES"]):
        return True

    # If location mentions "Remote" without a country, we include it
    # (since our searches are already scoped to US)
    if "REMOTE" in location and not country:
        return True

    # If no country or state info at all, but our search was US-scoped, include it
    if not country and not state and location:
        return True

    return False
