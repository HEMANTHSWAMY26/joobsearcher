# AP Job Posting Lead Generation System

> Automatically scrape US-based Accounts Payable job postings from multiple sources and push them to Google Sheets for outbound lead generation.

## Architecture

```
Tier 1: SerpAPI Google Jobs ─┐
Tier 2: RapidAPI JSearch ────┤──→ Normalize ──→ US Filter ──→ Deduplicate ──→ Google Sheets
Tier 3: Playwright (niche) ──┘                                                 ├── Master Tab
                                                                               └── Daily Tabs
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

For Tier 3 (niche board scraping), also install Playwright browsers:
```bash
playwright install chromium
```

### 2. Set Up API Keys

```bash
copy .env.example .env
```

Edit `.env` with your API keys:

| Key | Where to Get It | Required? |
|-----|----------------|-----------|
| `SERPAPI_API_KEY` | [serpapi.com](https://serpapi.com) → Sign Up → API Key | **Yes** (Primary) |
| `RAPIDAPI_KEY` | [rapidapi.com](https://rapidapi.com) → Subscribe to [JSearch](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) | Recommended |
| `GOOGLE_SHEET_ID` | Create a Sheet → copy ID from its URL | **Yes** |

### 3. Set Up Google Sheets API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable **Google Sheets API** and **Google Drive API**
4. Go to **Credentials** → **Create Credentials** → **Service Account**
5. Create a key (JSON format) and download it
6. Save the JSON file to `credentials/service_account.json`
7. Create a new Google Sheet
8. Share the sheet with the Service Account email (found in the JSON file under `client_email`)
9. Copy the Sheet ID from the URL and put it in `.env`

### 4. Run the Pipeline

```bash
# Full pipeline (all tiers)
python main.py

# Test mode (don't write to Sheets)
python main.py --dry-run

# Only Tier 1 (SerpAPI) — recommended for first run
python main.py --tier 1 --dry-run

# Single keyword test
python main.py --tier 1 --keyword "Accounts Payable" --location "United States" --dry-run
```

### 5. Set Up Daily Automation

```bash
# Create Windows Scheduled Task (run as Administrator)
python setup_scheduler.py create

# Check task status
python setup_scheduler.py status

# Remove task
python setup_scheduler.py delete
```

## Output

### Google Sheets Structure

| Tab | Description |
|-----|-------------|
| `MasterCompanies` | All-time aggregated list of companies — appended daily |
| `DailyJobs-25Feb2026` | Jobs found on that specific day (one tab per day) |

### Columns

Company Name, Job Title, Job Description, Job Location, City, State, Country, Employment Type, Experience Level, Posted Date, Job URL, Source, Company Size, Industry, Scraped At

## Project Structure

```
talk/
├── main.py                       # Entry point (orchestrator)
├── config.py                     # Keywords, API keys, settings
├── .env                          # Your API keys (from .env.example)
├── requirements.txt              # Python dependencies
├── setup_scheduler.py            # Windows Task Scheduler automation
├── scrapers/
│   ├── serpapi_google_jobs.py     # Tier 1: SerpAPI Google Jobs
│   ├── rapidapi_jsearch.py       # Tier 2: RapidAPI JSearch
│   └── playwright_scraper.py     # Tier 3: Direct niche board scraping
├── processing/
│   ├── normalizer.py             # Data normalization
│   ├── deduplicator.py           # SQLite-based dedup
│   └── us_filter.py              # US-only location filter
├── storage/
│   ├── sqlite_db.py              # Local dedup database
│   └── google_sheets.py          # Google Sheets writer
├── credentials/
│   └── service_account.json      # Google Service Account key
├── data/
│   └── jobs_dedup.db             # SQLite dedup DB (auto-created)
└── logs/
    └── run_YYYYMMDD_HHMMSS.log   # Per-run log files
```

## Cost to Hit 10,000 Leads/Week

| Item | Cost/Month |
|------|-----------|
| SerpAPI (Production plan) | ~$150 |
| RapidAPI JSearch (free tier) | $0 |
| Google Sheets API | Free |
| **Total** | **~$150/month** |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `SERPAPI_API_KEY not set` | Check `.env` file has the key |
| `Service account file not found` | Download from Google Cloud → `credentials/service_account.json` |
| `Google Sheets permission denied` | Share the Sheet with the service account email |
| `No jobs found` | Check your API key quotas; try `--dry-run` first |
| `Playwright not installed` | Run `pip install playwright && playwright install chromium` |
