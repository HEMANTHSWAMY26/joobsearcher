"""
WSGI entry point for Render/Gunicorn deployment.
Imports the Flask app from the dashboard module.
"""

import sys
import os
import logging

# Configure logging for Render
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stdout,
)

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger("wsgi")
logger.info("Starting AP Lead Gen Dashboard...")
logger.info(f"Python {sys.version}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"DATABASE_URL set: {bool(os.getenv('DATABASE_URL'))}")
logger.info(f"SERPAPI_API_KEY set: {bool(os.getenv('SERPAPI_API_KEY'))}")
logger.info(f"GOOGLE_SHEET_ID set: {bool(os.getenv('GOOGLE_SHEET_ID'))}")

try:
    from dashboard.app import app
    logger.info("Flask app loaded successfully!")
except Exception as e:
    logger.error(f"Failed to load app: {e}", exc_info=True)
    raise

if __name__ == "__main__":
    app.run()
