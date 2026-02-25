"""
Configuration for AP Job Posting Lead Generation System.
All keywords, search parameters, and constants live here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── API Keys ───────────────────────────────────────────────
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/service_account.json")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")  # For cloud: paste JSON content
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")

# ─── AP Keywords to Track ───────────────────────────────────
AP_KEYWORDS = [
    "Accounts Payable",
    "Accounts Payables",
    "Accounts Payable Clerk",
    "Accounts Payable Specialist",
    "Accounts Payable Analyst",
    "Accounts Payable Manager",
    "Full Cycle Accounts Payable",
]

# ─── US Metro Areas for Geographic Coverage ─────────────────
# We search across major US metros to maximize coverage.
# Google Jobs uses location to scope results.
US_LOCATIONS = [
    "United States",
    "New York, NY",
    "Los Angeles, CA",
    "Chicago, IL",
    "Houston, TX",
    "Phoenix, AZ",
    "Philadelphia, PA",
    "San Antonio, TX",
    "San Diego, CA",
    "Dallas, TX",
    "Austin, TX",
    "San Francisco, CA",
    "Seattle, WA",
    "Denver, CO",
    "Boston, MA",
    "Atlanta, GA",
    "Miami, FL",
    "Minneapolis, MN",
    "Charlotte, NC",
    "Detroit, MI",
    "Portland, OR",
    "Nashville, TN",
    "Salt Lake City, UT",
    "Kansas City, MO",
    "Columbus, OH",
    "Indianapolis, IN",
    "Cleveland, OH",
    "Pittsburgh, PA",
    "Cincinnati, OH",
    "Orlando, FL",
    "Tampa, FL",
    "St. Louis, MO",
    "Baltimore, MD",
    "Raleigh, NC",
    "Richmond, VA",
    "Milwaukee, WI",
]

# ─── Search Configuration ───────────────────────────────────
# SerpAPI Google Jobs chips parameter for date filtering
# "date_posted:today"  = last 24 hours
# "date_posted:3days"  = last 3 days
# "date_posted:week"   = last week
# "date_posted:month"  = last month
SERP_DATE_FILTER = "date_posted:week"

# Maximum pages to paginate per search (each page = 10 results)
SERP_MAX_PAGES = 5

# RapidAPI JSearch settings
JSEARCH_HOST = "jsearch.p.rapidapi.com"
JSEARCH_DATE_POSTED = "week"  # "today", "3days", "week", "month"
JSEARCH_MAX_PAGES = 5

# ─── Niche Boards for Playwright Scraping (Tier 3) ──────────
NICHE_BOARDS = [
    {
        "name": "jobright.ai",
        "base_url": "https://jobright.ai/jobs?searchKeyword={keyword}&location=United+States",
        "enabled": True,
    },
    {
        "name": "accountingcrossing.com",
        "base_url": "https://www.accountingcrossing.com/lcl-jbs-{keyword_slug}-jobs.html",
        "enabled": True,
    },
    {
        "name": "monster.com",
        "base_url": "https://www.monster.com/jobs/search?q={keyword}&where=United+States",
        "enabled": False,  # Usually covered by Google Jobs
    },
    {
        "name": "roberthalf.com",
        "base_url": "https://www.roberthalf.com/us/en/jobs?query={keyword}",
        "enabled": False,  # Usually covered by Google Jobs
    },
    {
        "name": "astoncarter.com",
        "base_url": "https://www.astoncarter.com/en/jobs?k={keyword}&l=United+States",
        "enabled": False,  # Usually covered by Google Jobs
    },
]

# ─── Google Sheets Config ───────────────────────────────────
MASTER_SHEET_NAME = "MasterCompanies"
DAILY_TAB_PREFIX = "DailyJobs-"  # e.g., "DailyJobs-25Feb2026"

# Column headers for the Google Sheet
SHEET_HEADERS = [
    "Company Name",
    "Job Title",
    "Job Description",
    "Job Location",
    "City",
    "State",
    "Country",
    "Employment Type",
    "Experience Level",
    "Posted Date",
    "Job URL",
    "Source",
    "Company Size",
    "Industry",
    "Scraped At",
]

# ─── Database Config ────────────────────────────────────────
SQLITE_DB_PATH = "data/jobs_dedup.db"

# ─── Scheduling ─────────────────────────────────────────────
# Time to run the daily scrape (24h format)
DAILY_RUN_TIME = "06:00"  # 6 AM local time

# ─── US States for Location Filtering ───────────────────────
US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

US_STATE_NAMES = {
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado",
    "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho",
    "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana",
    "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
    "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada",
    "New Hampshire", "New Jersey", "New Mexico", "New York",
    "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon",
    "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington",
    "West Virginia", "Wisconsin", "Wyoming", "District of Columbia",
}
