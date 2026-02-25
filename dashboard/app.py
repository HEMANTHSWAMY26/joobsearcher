"""
AP Lead Gen Dashboard — Flask API Backend

Provides a REST API and serves the web UI for:
- Viewing scraped jobs, stats, and pipeline status
- Triggering scrape runs from the browser
- Scheduling automated scrape runs
- Viewing Google Sheet links and dedup stats
"""

import os
import sys
import json
import subprocess
import threading
import time as _time
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template

try:
    import schedule
    SCHEDULE_AVAILABLE = True
except ImportError:
    SCHEDULE_AVAILABLE = False

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from config import (
    AP_KEYWORDS,
    US_LOCATIONS,
    SQLITE_DB_PATH,
    GOOGLE_SHEET_ID,
    SERPAPI_API_KEY,
    RAPIDAPI_KEY,
)
from storage.database import DatabaseManager

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    static_folder=os.path.join(DASHBOARD_DIR, "static"),
    template_folder=os.path.join(DASHBOARD_DIR, "templates"),
)

# Initialize database (auto-selects SQLite or Neon PostgreSQL)
db = DatabaseManager(os.path.join(PROJECT_ROOT, SQLITE_DB_PATH))

# Track running scrape jobs
scrape_status = {
    "running": False,
    "started_at": None,
    "last_run": None,
    "last_result": None,
    "log_output": "",
}


# ─── Web UI ─────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ─── Stats API ──────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    try:
        stats = db.get_stats()
        today = datetime.now().strftime("%Y-%m-%d")
        # Get today's count through daily counts
        daily = db.get_daily_counts(1)
        today_count = daily[0]["count"] if daily and daily[0]["date"] == today else 0

        return jsonify({
            "total_jobs": stats["total_seen"],
            "unique_companies": stats["unique_companies"],
            "sources": stats["by_source"],
            "today_count": today_count,
            "db_exists": True,
        })
    except Exception as e:
        return jsonify({"total_jobs": 0, "unique_companies": 0, "sources": {}, "today_count": 0, "error": str(e)})


@app.route("/api/jobs")
def api_jobs():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)
    search = request.args.get("search", "").strip()
    source = request.args.get("source", "").strip()

    try:
        result = db.query_jobs(search=search, source=source, page=page, per_page=per_page)
        return jsonify(result)
    except Exception as e:
        return jsonify({"jobs": [], "total": 0, "page": 1, "pages": 0, "error": str(e)})


@app.route("/api/jobs/daily")
def api_daily_jobs():
    try:
        days = db.get_daily_counts()
        return jsonify({"days": days})
    except Exception as e:
        return jsonify({"days": [], "error": str(e)})


@app.route("/api/sources")
def api_sources():
    try:
        sources = db.get_sources()
        return jsonify({"sources": sources})
    except Exception as e:
        return jsonify({"sources": [], "error": str(e)})


@app.route("/api/config")
def api_config():
    return jsonify({
        "keywords": AP_KEYWORDS,
        "locations_count": len(US_LOCATIONS),
        "locations_sample": US_LOCATIONS[:5],
        "serpapi_configured": bool(SERPAPI_API_KEY),
        "rapidapi_configured": bool(RAPIDAPI_KEY),
        "sheet_id": GOOGLE_SHEET_ID,
        "sheet_url": f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit" if GOOGLE_SHEET_ID else None,
    })


# ─── Scrape Trigger ─────────────────────────────────────────

@app.route("/api/scrape", methods=["POST"])
def api_trigger_scrape():
    if scrape_status["running"]:
        return jsonify({"error": "A scrape is already running", "status": scrape_status}), 409

    data = request.get_json() or {}
    tier = data.get("tier", [1])
    keywords = data.get("keywords", None)
    dry_run = data.get("dry_run", False)

    cmd = [sys.executable, os.path.join(PROJECT_ROOT, "main.py")]
    cmd.extend(["--tier"] + [str(t) for t in tier])
    if keywords:
        cmd.extend(["--keyword"] + keywords)
    if dry_run:
        cmd.append("--dry-run")

    def run_scrape():
        scrape_status["running"] = True
        scrape_status["started_at"] = datetime.now().isoformat()
        scrape_status["log_output"] = ""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=600)
            scrape_status["log_output"] = result.stdout + result.stderr
            scrape_status["last_result"] = "success" if result.returncode == 0 else "error"
        except subprocess.TimeoutExpired:
            scrape_status["last_result"] = "timeout"
            scrape_status["log_output"] += "\n[TIMEOUT] Scrape exceeded 10 minute limit."
        except Exception as e:
            scrape_status["last_result"] = "error"
            scrape_status["log_output"] += f"\n[ERROR] {str(e)}"
        finally:
            scrape_status["running"] = False
            scrape_status["last_run"] = datetime.now().isoformat()

    threading.Thread(target=run_scrape, daemon=True).start()
    return jsonify({"message": "Scrape started", "command": " ".join(cmd), "status": scrape_status})


@app.route("/api/scrape/status")
def api_scrape_status():
    return jsonify(scrape_status)


# ─── Scheduler ──────────────────────────────────────────────

SCHEDULER_FILE = os.path.join(PROJECT_ROOT, "data", "scheduler.json")

scheduler_state = {
    "active": False,
    "paused": False,
    "frequency": "daily",
    "time": "06:00",
    "tiers": [1],
    "next_run": None,
}

scheduler_stop_event = threading.Event()


def load_scheduler_state():
    global scheduler_state
    try:
        if os.path.exists(SCHEDULER_FILE):
            with open(SCHEDULER_FILE, "r") as f:
                scheduler_state.update(json.load(f))
    except Exception:
        pass


def save_scheduler_state():
    os.makedirs(os.path.dirname(SCHEDULER_FILE), exist_ok=True)
    with open(SCHEDULER_FILE, "w") as f:
        json.dump(scheduler_state, f, indent=2)


def run_scheduled_scrape():
    if scrape_status["running"]:
        return
    tiers = scheduler_state.get("tiers", [1])
    cmd = [sys.executable, os.path.join(PROJECT_ROOT, "main.py")]
    cmd.extend(["--tier"] + [str(t) for t in tiers])

    def _run():
        scrape_status["running"] = True
        scrape_status["started_at"] = datetime.now().isoformat()
        scrape_status["log_output"] = ""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=600)
            scrape_status["log_output"] = result.stdout + result.stderr
            scrape_status["last_result"] = "success" if result.returncode == 0 else "error"
        except Exception as e:
            scrape_status["last_result"] = "error"
            scrape_status["log_output"] += f"\n[ERROR] {str(e)}"
        finally:
            scrape_status["running"] = False
            scrape_status["last_run"] = datetime.now().isoformat()

    threading.Thread(target=_run, daemon=True).start()


def scheduler_loop():
    while not scheduler_stop_event.is_set():
        if SCHEDULE_AVAILABLE and scheduler_state["active"] and not scheduler_state["paused"]:
            schedule.run_pending()
        _time.sleep(30)


def setup_schedule():
    if not SCHEDULE_AVAILABLE:
        return
    schedule.clear()
    if not scheduler_state["active"] or scheduler_state["paused"]:
        return

    freq = scheduler_state["frequency"]
    run_time = scheduler_state.get("time", "06:00")

    if freq == "daily":
        schedule.every().day.at(run_time).do(run_scheduled_scrape)
    elif freq == "twice_daily":
        schedule.every().day.at("06:00").do(run_scheduled_scrape)
        schedule.every().day.at("18:00").do(run_scheduled_scrape)
    elif freq == "every_6h":
        schedule.every(6).hours.do(run_scheduled_scrape)
    elif freq == "hourly":
        schedule.every(1).hours.do(run_scheduled_scrape)

    next_job = schedule.next_run()
    if next_job:
        scheduler_state["next_run"] = next_job.isoformat()


@app.route("/api/scheduler/status")
def api_scheduler_status():
    if SCHEDULE_AVAILABLE:
        next_job = schedule.next_run()
        if next_job:
            scheduler_state["next_run"] = next_job.isoformat()
    return jsonify(scheduler_state)


@app.route("/api/scheduler/save", methods=["POST"])
def api_scheduler_save():
    data = request.get_json() or {}
    scheduler_state["frequency"] = data.get("frequency", "daily")
    scheduler_state["time"] = data.get("time", "06:00")
    scheduler_state["tiers"] = data.get("tiers", [1])
    scheduler_state["active"] = True
    scheduler_state["paused"] = False
    setup_schedule()
    save_scheduler_state()
    return jsonify({**scheduler_state, "message": f"Scheduled {scheduler_state['frequency']} at {scheduler_state['time']}"})


@app.route("/api/scheduler/pause", methods=["POST"])
def api_scheduler_pause():
    scheduler_state["paused"] = True
    if SCHEDULE_AVAILABLE:
        schedule.clear()
    save_scheduler_state()
    return jsonify(scheduler_state)


@app.route("/api/scheduler/resume", methods=["POST"])
def api_scheduler_resume():
    scheduler_state["paused"] = False
    setup_schedule()
    save_scheduler_state()
    return jsonify(scheduler_state)


# ─── Startup ────────────────────────────────────────────────

def start_background_services():
    load_scheduler_state()
    setup_schedule()
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()


start_background_services()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 60)
    print("  ⚡ AP Lead Gen Dashboard")
    print("=" * 60)
    print(f"  🌐  http://localhost:{port}")
    print(f"  📊  Sheet: https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/edit")
    print(f"  🔑  SerpAPI: {'✅' if SERPAPI_API_KEY else '❌'}")
    print(f"  🗄️  DB: {'PostgreSQL (Neon)' if db.use_postgres else 'SQLite'}")
    print(f"  ⏰  Scheduler: {'✅ Active' if scheduler_state['active'] else '❌ Inactive'}")
    print("=" * 60 + "\n")
    app.run(debug=True, host="0.0.0.0", port=port)
