"""
api.py  —  Flask REST API for the Job Hunter frontend
Endpoints:
  GET  /api/status          — pipeline status & last run info
  POST /api/run             — trigger a full pipeline run (background)
  GET  /api/jobs            — list all jobs from Google Sheet
  GET  /api/jobs/<job_hash> — single job detail + cover letter content
  POST /api/jobs/<job_hash>/apply  — mark job as applied
  GET  /api/logs            — last 100 lines of today's log
"""

import json
import os
import subprocess
import threading
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Silence werkzeug request logs — they clutter the terminal and the app log file.
# Flask HTTP traffic goes nowhere; only app-level errors (500s) still surface.
import logging as _logging
_wz = _logging.getLogger("werkzeug")
_wz.setLevel(_logging.ERROR)   # only show actual server errors, not GET /api/jobs 200
_wz.propagate = False

SHEET_ID   = os.getenv("SHEET_ID", "")
LOG_DIR    = Path("logs")
CL_DIR     = Path("cover_letters")

# ── Pipeline run state ────────────────────────────────────────────────────
_run_state = {
    "running": False,
    "last_run": None,
    "last_status": "never",   # never | running | success | error
    "last_message": "",
    "jobs_found": 0,
    "jobs_kept": 0,
}
_run_lock = threading.Lock()


def _run_pipeline_thread():
    global _run_state
    with _run_lock:
        _run_state["running"]  = True
        _run_state["last_status"] = "running"
        _run_state["last_message"] = "Pipeline started…"

    try:
        # Import here so env is already loaded
        from main import run
        run()
        with _run_lock:
            _run_state["last_status"]  = "success"
            _run_state["last_message"] = "Pipeline completed successfully."
            _run_state["last_run"]     = date.today().isoformat()
    except Exception as e:
        with _run_lock:
            _run_state["last_status"]  = "error"
            _run_state["last_message"] = str(e)[:300]
    finally:
        with _run_lock:
            _run_state["running"] = False


# ── Sheet reader (lightweight — avoids re-importing all of main) ──────────

def _read_sheet_jobs():
    """Read all rows from Google Sheet Applications tab."""
    try:
        from storage.sheets import COLUMN_ORDER
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "google_credentials.json")
        creds = service_account.Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
        result = (
            svc.spreadsheets().values()
            .get(spreadsheetId=SHEET_ID, range="Applications!A:AZ")
            .execute()
        )
        rows = result.get("values", [])
        if len(rows) < 2:
            return []

        header = rows[0]
        jobs   = []
        for row in rows[1:]:
            # Pad short rows
            padded = row + [""] * (len(header) - len(row))
            job    = dict(zip(header, padded))
            jobs.append(job)
        return jobs
    except Exception as e:
        return {"error": str(e)}


def _read_local_cover_letter(job_hash: str) -> str:
    """Read a cover letter from local cover_letters/ dir by job hash prefix."""
    if not job_hash:
        return ""
    for path in CL_DIR.glob("*.md"):
        if job_hash[:8] in path.name or job_hash in path.name:
            return path.read_text(encoding="utf-8")
    return ""


def _tail_log(n: int = 200) -> str:
    """Return the last n lines of the most recent app log file."""
    if not LOG_DIR.exists():
        return "No logs directory yet. Run the pipeline first."

    log_file = LOG_DIR / f"run_{date.today().isoformat()}.log"
    if not log_file.exists():
        logs = sorted(LOG_DIR.glob("run_*.log"), reverse=True)
        if not logs:
            return "No log files found yet. Run the pipeline to generate logs."
        log_file = logs[0]

    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        # Filter out blank lines and werkzeug noise that slipped through
        lines = [l for l in lines if l.strip() and "werkzeug" not in l]
        return "\n".join(lines[-n:])
    except Exception as e:
        return f"Error reading log file: {e}"


# ── Routes ────────────────────────────────────────────────────────────────

@app.get("/api/status")
def get_status():
    return jsonify(_run_state)


@app.post("/api/run")
def trigger_run():
    with _run_lock:
        if _run_state["running"]:
            return jsonify({"ok": False, "message": "Pipeline already running."}), 409
    t = threading.Thread(target=_run_pipeline_thread, daemon=True)
    t.start()
    return jsonify({"ok": True, "message": "Pipeline started."})


@app.get("/api/jobs")
def list_jobs():
    jobs = _read_sheet_jobs()
    if isinstance(jobs, dict) and "error" in jobs:
        return jsonify(jobs), 500
    return jsonify(jobs)


@app.get("/api/jobs/<job_hash>")
def get_job(job_hash):
    jobs = _read_sheet_jobs()
    if isinstance(jobs, dict) and "error" in jobs:
        return jsonify(jobs), 500
    match = next((j for j in jobs if j.get("Job Hash", "") == job_hash), None)
    if not match:
        return jsonify({"error": "Not found"}), 404
    match["cover_letter_text"] = _read_local_cover_letter(job_hash)
    return jsonify(match)


@app.post("/api/jobs/<job_hash>/apply")
def mark_applied(job_hash):
    # In a full implementation this would update the Sheet row.
    # For now it returns success so the frontend can optimistically update.
    return jsonify({"ok": True, "job_hash": job_hash})


@app.get("/api/logs")
def get_logs():
    return jsonify({"logs": _tail_log(100)})


if __name__ == "__main__":
    app.run(port=5000, debug=False)
