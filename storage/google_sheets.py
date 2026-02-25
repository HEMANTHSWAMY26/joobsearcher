"""
Google Sheets Writer — writes job data to Google Sheets using gspread.

Manages two types of sheets:
1. Master Sheet: Aggregated companies list, appended to daily
2. Daily Tabs: One tab per day with format "DailyJobs-25Feb2026"
"""

import logging
import json
from datetime import datetime
from typing import Optional

import gspread
from google.oauth2.service_account import Credentials

from config import (
    GOOGLE_SERVICE_ACCOUNT_FILE,
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SHEET_ID,
    MASTER_SHEET_NAME,
    DAILY_TAB_PREFIX,
    SHEET_HEADERS,
)

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class GoogleSheetsWriter:
    """Writes job data to Google Sheets with Master + Daily tab architecture."""

    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self._initialized = False

    def initialize(self) -> bool:
        """
        Initialize the Google Sheets connection.
        Supports both file-based credentials (local) and JSON string credentials (cloud/Render).
        """
        try:
            if not GOOGLE_SHEET_ID:
                logger.error("GOOGLE_SHEET_ID is not set. Cannot write to Google Sheets.")
                return False

            # Try env var first (for cloud deployment), then fall back to file
            if GOOGLE_SERVICE_ACCOUNT_JSON:
                info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
                creds = Credentials.from_service_account_info(info, scopes=SCOPES)
                logger.info("Using service account from GOOGLE_SERVICE_ACCOUNT_JSON env var")
            else:
                creds = Credentials.from_service_account_file(
                    GOOGLE_SERVICE_ACCOUNT_FILE, scopes=SCOPES,
                )
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(GOOGLE_SHEET_ID)
            self._initialized = True
            logger.info(f"Google Sheets connected: {self.spreadsheet.title}")
            return True

        except FileNotFoundError:
            logger.error(
                f"Service account file not found: {GOOGLE_SERVICE_ACCOUNT_FILE}. "
                f"Download it from Google Cloud Console and place it in the credentials/ folder."
            )
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets: {e}")
            return False

    def write_jobs(self, jobs: list[dict]) -> int:
        """
        Write new jobs to both the Master sheet and today's Daily tab.

        Args:
            jobs: List of normalized job dicts to write.

        Returns:
            Number of rows successfully written.
        """
        if not self._initialized:
            logger.error("Google Sheets not initialized. Call initialize() first.")
            return 0

        if not jobs:
            logger.info("No jobs to write.")
            return 0

        # Convert jobs to rows
        rows = [self._job_to_row(job) for job in jobs]

        written = 0

        # Write to Master sheet
        try:
            master = self._get_or_create_worksheet(MASTER_SHEET_NAME)
            self._append_rows(master, rows)
            logger.info(f"Appended {len(rows)} rows to Master sheet")
            written += len(rows)
        except Exception as e:
            logger.error(f"Error writing to Master sheet: {e}")

        # Write to Daily tab
        try:
            daily_name = self._get_daily_tab_name()
            daily = self._get_or_create_worksheet(daily_name)
            self._append_rows(daily, rows)
            logger.info(f"Appended {len(rows)} rows to {daily_name}")
        except Exception as e:
            logger.error(f"Error writing to Daily tab: {e}")

        return written

    def _get_or_create_worksheet(self, name: str) -> gspread.Worksheet:
        """
        Get an existing worksheet by name, or create it with headers.
        """
        try:
            worksheet = self.spreadsheet.worksheet(name)
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            logger.info(f"Creating new worksheet: {name}")
            worksheet = self.spreadsheet.add_worksheet(
                title=name,
                rows=1000,
                cols=len(SHEET_HEADERS),
            )
            # Add headers
            worksheet.append_row(SHEET_HEADERS)

            # Format headers (bold)
            try:
                worksheet.format("1:1", {
                    "textFormat": {"bold": True},
                    "backgroundColor": {"red": 0.2, "green": 0.4, "blue": 0.8},
                    "horizontalAlignment": "CENTER",
                })
            except Exception:
                pass  # Formatting is nice-to-have, not critical

            return worksheet

    def _append_rows(self, worksheet: gspread.Worksheet, rows: list[list]):
        """
        Append multiple rows to a worksheet. Batches writes for efficiency.
        Google Sheets API has a limit of ~10MB per request.
        """
        BATCH_SIZE = 100  # Rows per batch to avoid API limits

        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            try:
                worksheet.append_rows(
                    batch,
                    value_input_option="USER_ENTERED",
                    insert_data_option="INSERT_ROWS",
                )
                logger.debug(f"Wrote batch of {len(batch)} rows")
            except gspread.exceptions.APIError as e:
                if "quota" in str(e).lower() or "rate" in str(e).lower():
                    logger.warning("Google Sheets API rate limit hit. Waiting 60s...")
                    import time
                    time.sleep(60)
                    # Retry once
                    worksheet.append_rows(
                        batch,
                        value_input_option="USER_ENTERED",
                        insert_data_option="INSERT_ROWS",
                    )
                else:
                    raise

    def _job_to_row(self, job: dict) -> list:
        """Convert a job dict to a list of values matching SHEET_HEADERS."""
        return [
            job.get("company_name", ""),
            job.get("job_title", ""),
            job.get("job_description", "")[:2000],  # Truncate for Sheets cell limit
            job.get("job_location", ""),
            job.get("city", ""),
            job.get("state", ""),
            job.get("country", ""),
            job.get("employment_type", ""),
            job.get("experience_level", ""),
            job.get("posted_date", ""),
            job.get("job_url", ""),
            job.get("source", ""),
            job.get("company_size", ""),
            job.get("industry", ""),
            job.get("scraped_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        ]

    @staticmethod
    def _get_daily_tab_name() -> str:
        """
        Generate today's daily tab name.
        Format: DailyJobs-25Feb2026
        """
        return f"{DAILY_TAB_PREFIX}{datetime.now().strftime('%d%b%Y')}"

    def get_sheet_info(self) -> Optional[dict]:
        """Get basic info about the spreadsheet."""
        if not self._initialized:
            return None

        worksheets = self.spreadsheet.worksheets()
        return {
            "title": self.spreadsheet.title,
            "url": self.spreadsheet.url,
            "worksheets": [ws.title for ws in worksheets],
            "total_worksheets": len(worksheets),
        }
