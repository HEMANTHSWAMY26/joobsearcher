"""
WSGI entry point for Render/Gunicorn deployment.
Imports the Flask app from the dashboard module.
"""

import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dashboard.app import app

if __name__ == "__main__":
    app.run()
