"""
Tier 3 — Playwright Direct Scraper (Niche Job Boards)

Used for boards not well-indexed by Google Jobs:
- jobright.ai
- accountingcrossing.com
- monster.com (if needed)

Uses headless browser automation with anti-detection measures.
"""

import logging
import asyncio
import time
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Playwright is optional — import gracefully
try:
    from playwright.async_api import async_playwright, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Tier 3 scraping disabled. Run: pip install playwright && playwright install chromium")


async def scrape_jobright(keyword: str) -> list[dict]:
    """
    Scrape job listings from jobright.ai for a given keyword.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return []

    jobs = []
    url = f"https://jobright.ai/jobs?searchKeyword={keyword.replace(' ', '+')}&location=United+States"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            logger.info(f"Playwright: Scraping jobright.ai for '{keyword}'")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)  # Let dynamic content load

            # Scroll to load more results
            for _ in range(5):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)

            # Extract job cards — adjust selectors based on site structure
            job_cards = await page.query_selector_all('[class*="job-card"], [class*="JobCard"], [data-testid*="job"]')

            if not job_cards:
                # Fallback: try to find any list items that look like jobs
                job_cards = await page.query_selector_all('a[href*="/jobs/"]')

            for card in job_cards[:50]:  # Cap at 50 per search
                try:
                    text = await card.inner_text()
                    href = await card.get_attribute("href") or ""

                    if not text.strip():
                        continue

                    parsed = _parse_generic_job_card(text, href, "jobright.ai", keyword)
                    if parsed:
                        jobs.append(parsed)
                except Exception:
                    continue

            await browser.close()
            logger.info(f"Playwright: Found {len(jobs)} jobs on jobright.ai")

    except Exception as e:
        logger.error(f"Playwright error scraping jobright.ai: {e}")

    return jobs


async def scrape_accountingcrossing(keyword: str) -> list[dict]:
    """
    Scrape job listings from accountingcrossing.com.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return []

    jobs = []
    keyword_slug = keyword.lower().replace(" ", "-")
    url = f"https://www.accountingcrossing.com/jobs/q-{keyword_slug}-jobs.html"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            logger.info(f"Playwright: Scraping accountingcrossing.com for '{keyword}'")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)

            # Extract job listings
            job_cards = await page.query_selector_all('.job-listing, .job-item, [class*="job"], tr[class*="job"]')

            for card in job_cards[:50]:
                try:
                    text = await card.inner_text()
                    link_el = await card.query_selector("a[href]")
                    href = ""
                    if link_el:
                        href = await link_el.get_attribute("href") or ""
                        if href and not href.startswith("http"):
                            href = f"https://www.accountingcrossing.com{href}"

                    parsed = _parse_generic_job_card(text, href, "accountingcrossing.com", keyword)
                    if parsed:
                        jobs.append(parsed)
                except Exception:
                    continue

            await browser.close()
            logger.info(f"Playwright: Found {len(jobs)} jobs on accountingcrossing.com")

    except Exception as e:
        logger.error(f"Playwright error scraping accountingcrossing.com: {e}")

    return jobs


async def scrape_monster(keyword: str) -> list[dict]:
    """
    Scrape job listings from monster.com.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return []

    jobs = []
    url = f"https://www.monster.com/jobs/search?q={keyword.replace(' ', '+')}&where=United+States"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            logger.info(f"Playwright: Scraping monster.com for '{keyword}'")
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)

            job_cards = await page.query_selector_all('[data-testid="svx-job-card"], .job-cardstyle, [class*="JobCard"]')

            for card in job_cards[:50]:
                try:
                    text = await card.inner_text()
                    link_el = await card.query_selector("a[href]")
                    href = ""
                    if link_el:
                        href = await link_el.get_attribute("href") or ""

                    parsed = _parse_generic_job_card(text, href, "monster.com", keyword)
                    if parsed:
                        jobs.append(parsed)
                except Exception:
                    continue

            await browser.close()
            logger.info(f"Playwright: Found {len(jobs)} jobs on monster.com")

    except Exception as e:
        logger.error(f"Playwright error scraping monster.com: {e}")

    return jobs


def _parse_generic_job_card(text: str, url: str, source: str, keyword: str) -> Optional[dict]:
    """
    Parse a generic job card's text content into our common schema.
    This is a best-effort parser since each site has different formats.
    """
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]

    if len(lines) < 2:
        return None

    # Typically: first line = title, second line = company, third = location
    title = lines[0] if len(lines) > 0 else ""
    company = lines[1] if len(lines) > 1 else ""
    location_raw = lines[2] if len(lines) > 2 else ""

    # Basic validation — title should contain AP-related keywords
    title_lower = title.lower()
    if not any(kw in title_lower for kw in ["account", "payable", "ap ", "a/p"]):
        # Might be the company in line 0 and title in line 1
        title, company = company, title
        title_lower = title.lower()
        if not any(kw in title_lower for kw in ["account", "payable", "ap ", "a/p"]):
            return None

    # Parse location
    city, state, country = "", "", "US"
    if location_raw:
        parts = [p.strip() for p in location_raw.split(",")]
        if len(parts) >= 1:
            city = parts[0]
        if len(parts) >= 2:
            state = parts[1]

    # Get remaining text as description snippet
    description = " ".join(lines[3:])[:2000] if len(lines) > 3 else ""

    return {
        "company_name": company[:200],
        "job_title": title[:200],
        "job_description": description,
        "job_location": location_raw,
        "city": city,
        "state": state,
        "country": country,
        "employment_type": "",
        "experience_level": "",
        "posted_date": "",
        "job_url": url,
        "source": source,
        "company_size": "",
        "industry": "",
        "job_id": url,  # Use URL as ID for niche boards
        "search_keyword": keyword,
    }


def run_niche_scraping(keyword: str, boards: list[dict]) -> list[dict]:
    """
    Synchronous wrapper to run async Playwright scrapers.

    Args:
        keyword: Search keyword
        boards: List of board config dicts from config.NICHE_BOARDS

    Returns:
        Combined list of jobs from all enabled niche boards.
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning("Playwright not available. Skipping niche board scraping.")
        return []

    all_jobs = []

    for board in boards:
        if not board.get("enabled", False):
            continue

        name = board["name"]
        try:
            if "jobright" in name:
                jobs = asyncio.run(scrape_jobright(keyword))
            elif "accountingcrossing" in name:
                jobs = asyncio.run(scrape_accountingcrossing(keyword))
            elif "monster" in name:
                jobs = asyncio.run(scrape_monster(keyword))
            else:
                logger.warning(f"No scraper implemented for {name}")
                continue

            all_jobs.extend(jobs)
            time.sleep(3)  # Be polite between sites

        except Exception as e:
            logger.error(f"Error scraping {name}: {e}")

    return all_jobs
