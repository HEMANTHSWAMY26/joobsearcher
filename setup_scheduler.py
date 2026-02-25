"""
Windows Task Scheduler Setup — automates daily pipeline runs.

Creates a Windows Scheduled Task that runs main.py daily at the configured time.
"""

import subprocess
import sys
import os
import logging

from config import DAILY_RUN_TIME

logger = logging.getLogger(__name__)

TASK_NAME = "AP_LeadGen_Daily_Scrape"


def create_scheduled_task():
    """
    Create a Windows Scheduled Task to run the pipeline daily.
    Requires administrative privileges.
    """
    python_path = sys.executable
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    working_dir = os.path.dirname(os.path.abspath(__file__))

    # Parse time
    hour, minute = DAILY_RUN_TIME.split(":")

    # Build the schtasks command
    cmd = [
        "schtasks",
        "/Create",
        "/TN", TASK_NAME,
        "/TR", f'"{python_path}" "{script_path}"',
        "/SC", "DAILY",
        "/ST", f"{hour}:{minute}",
        "/SD", "02/25/2026",  # Start date
        "/F",  # Force overwrite if exists
        "/RL", "HIGHEST",  # Run with highest privileges
    ]

    print(f"\n{'='*60}")
    print(f"Creating Windows Scheduled Task: {TASK_NAME}")
    print(f"{'='*60}")
    print(f"Python:      {python_path}")
    print(f"Script:      {script_path}")
    print(f"Working Dir: {working_dir}")
    print(f"Schedule:    Daily at {DAILY_RUN_TIME}")
    print(f"{'='*60}\n")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            shell=True,
        )

        if result.returncode == 0:
            print(f"✅ Task '{TASK_NAME}' created successfully!")
            print(f"\nThe pipeline will run daily at {DAILY_RUN_TIME}.")
            print(f"\nTo manage the task:")
            print(f"  View:    schtasks /Query /TN {TASK_NAME}")
            print(f"  Run now: schtasks /Run /TN {TASK_NAME}")
            print(f"  Delete:  schtasks /Delete /TN {TASK_NAME} /F")
        else:
            print(f"❌ Failed to create task.")
            print(f"Error: {result.stderr}")
            print(f"\nTip: Try running this script as Administrator.")

    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"\nAlternative: Set up manually in Task Scheduler:")
        print(f"  1. Open Task Scheduler (taskschd.msc)")
        print(f"  2. Create Basic Task → Name: {TASK_NAME}")
        print(f"  3. Trigger: Daily at {DAILY_RUN_TIME}")
        print(f'  4. Action: Start a Program → "{python_path}" "{script_path}"')
        print(f"  5. Set 'Start in' to: {working_dir}")


def delete_scheduled_task():
    """Delete the scheduled task."""
    try:
        result = subprocess.run(
            ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
            capture_output=True,
            text=True,
            shell=True,
        )
        if result.returncode == 0:
            print(f"✅ Task '{TASK_NAME}' deleted.")
        else:
            print(f"Task not found or already deleted.")
    except Exception as e:
        print(f"Error: {e}")


def check_task_status():
    """Check if the scheduled task exists and its status."""
    try:
        result = subprocess.run(
            ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V"],
            capture_output=True,
            text=True,
            shell=True,
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"Task '{TASK_NAME}' not found.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage the daily scraping scheduled task")
    parser.add_argument("action", choices=["create", "delete", "status"],
                        help="Action to perform")
    args = parser.parse_args()

    if args.action == "create":
        create_scheduled_task()
    elif args.action == "delete":
        delete_scheduled_task()
    elif args.action == "status":
        check_task_status()
