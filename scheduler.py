"""
scheduler.py
────────────
Runs the pipeline on a schedule — mirrors the n8n Schedule Trigger node:
  "Every 3 days at 7:00 AM"

Usage:
    python scheduler.py           # runs in foreground, Ctrl+C to stop
    nohup python scheduler.py &   # background on Linux/Mac
"""

import logging
import sys
import time
from datetime import datetime

import schedule
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("scheduler")


def _run_pipeline():
    logger.info("⏰ Scheduled run triggered — starting pipeline …")
    try:
        # Import here so any import errors are caught per-run
        from main import run
        run()
    except Exception as e:
        logger.exception(f"Pipeline run failed: {e}")


# ── Schedule: every 3 days at 07:00 ─────────────────────────────────────
# `schedule` library doesn't support "every N days at HH:MM" natively,
# so we use a daily check and track the last run day.

_last_run_day: int = -1


def _maybe_run():
    global _last_run_day
    now = datetime.now()
    # Run on days 0, 3, 6, 9, … of the month (approximation of every 3 days)
    if now.hour == 7 and now.day % 3 == 0 and now.day != _last_run_day:
        _last_run_day = now.day
        _run_pipeline()


schedule.every().hour.at(":00").do(_maybe_run)


if __name__ == "__main__":
    logger.info("📅 Scheduler started — pipeline runs every 3 days at 07:00.")
    logger.info("   Press Ctrl+C to stop.")

    # Run immediately on first start if you want (uncomment below):
    # logger.info("Running immediately on start …")
    # _run_pipeline()

    while True:
        schedule.run_pending()
        time.sleep(60)
