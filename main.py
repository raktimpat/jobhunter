"""
main.py
───────
Full job hunting pipeline — local Python replacement for the n8n workflow.

Pipeline (mirrors the n8n workflow node-by-node):
  1. Schedule trigger          → runs on a schedule (see scheduler.py)
  2. linkedin_actor            → scrapers/linkedin.py
  3. normalize_fields          → utils/normalizer.py
  4. generate_hashes           → utils/hashing.py
  5. read_seen_hashes          → storage/sheets.py
  6. Merge + filter_unseen     → in-memory set subtraction
  7. prepare_score_batch       → builds compact batch
  8. bulk_scorer_agent         → agents/scorer.py
  9. parse_and_sort            → already done inside scorer.py
  10. Loop Over Items:
       a. jd_extractor_agent   → agents/jd_extractor.py
       b. parse_jd_json        → done inside jd_extractor.py
       c. Download file        → storage/drive.py (master_resume.json)
       d. cover_letter_writer  → agents/cover_letter.py
       e. parse_cover_letter   → done inside cover_letter.py
       f. encode + Upload file → storage/drive.py
       g. Share file           → storage/drive.py
       h. Append row           → storage/sheets.py
  11. Slack notification       → utils/notify.py
"""

import json
import logging
import os
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

env_path = Path(r"C:\Users\XqizIT\Desktop\JobHunter\new\job_hunter\.env")

loaded = load_dotenv(env_path, override=True)

# ── Logging setup ────────────────────────────────────────────────────────
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"run_{date.today().isoformat()}.log"

_fmt  = logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s")
_fh   = logging.FileHandler(log_file, encoding="utf-8")
_sh   = logging.StreamHandler(sys.stdout)
_fh.setFormatter(_fmt)
_sh.setFormatter(_fmt)

root = logging.getLogger()
root.setLevel(logging.INFO)
root.addHandler(_fh)
root.addHandler(_sh)

# Silence Flask/Werkzeug so HTTP request lines never pollute the app log
for _noisy in ("werkzeug", "flask", "flask.app", "urllib3", "googleapiclient", "httpx", "httpcore", "google_genai.models", "google.auth.transport"):
    _lg = logging.getLogger(_noisy)
    _lg.setLevel(logging.WARNING)
    _lg.propagate = False
logger = logging.getLogger("pipeline")


# ── Imports (after env is loaded) ────────────────────────────────────────
from config.search_targets import SEARCH_URLS
from scrapers.linkedin import scrape_jobs
from utils.normalizer import normalize_job
from utils.hashing import compute_job_hash
from utils.notify import notify_no_new_jobs, notify_summary, notify_error
from agents.scorer import score_jobs
from agents.jd_extractor import extract_jd
from agents.cover_letter import write_cover_letter
from storage.sheets import read_seen_hashes, append_job_row, ensure_header_row
from storage.drive import (
    download_resume, upload_cover_letter, share_file_public,
    build_cover_letter_filename,
)


# ── Config ────────────────────────────────────────────────────────────────
SHEET_ID       = os.environ["SHEET_ID"]
DRIVE_FOLDER   = os.environ["DRIVE_FOLDER_ID"]
RESUME_FILE_ID = os.environ["RESUME_FILE_ID"]
MAX_ITEMS      = int(os.getenv("MAX_ITEMS", "200"))
TODAY          = date.today().isoformat()


def load_local_resume() -> Optional[dict]:
    """Fallback: load resume from local file if Drive fails."""
    path = Path("data/master_resume.json")
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("[Resume] Loaded from local data/master_resume.json")
        return data
    return None


def run() -> None:
    start = datetime.now()
    logger.info("=" * 60)
    logger.info("🚀 Job Hunter pipeline starting")
    logger.info(f"   Date: {TODAY}  |  Max items: {MAX_ITEMS}")
    logger.info("=" * 60)

    # ── Step 1: Ensure Google Sheet header exists ─────────────────────────
    logger.info("Step 1 — Ensuring Google Sheet header row …")
    ensure_header_row(SHEET_ID)

    # ── Step 2: Scrape LinkedIn ───────────────────────────────────────────
    logger.info(f"Step 2 — Scraping LinkedIn ({len(SEARCH_URLS)} search URLs) …")
    raw_jobs = scrape_jobs(SEARCH_URLS, max_items=MAX_ITEMS)
    logger.info(f"         → {len(raw_jobs)} raw jobs scraped")

    if not raw_jobs:
        logger.warning("No jobs scraped. Exiting.")
        notify_no_new_jobs()
        return

    # ── Step 3: Normalize ────────────────────────────────────────────────
    logger.info("Step 3 — Normalizing job fields …")
    normalized = []
    for raw in raw_jobs:
        job = normalize_job(raw)
        if job:
            normalized.append(job)
    logger.info(f"         → {len(normalized)} jobs after normalization")

    # ── Step 4: Generate FNV hashes ──────────────────────────────────────
    logger.info("Step 4 — Generating FNV hashes …")
    for job in normalized:
        job["job_hash"] = compute_job_hash(
            job.get("title", ""),
            job.get("company", ""),
            job.get("location", ""),
        )

    # ── Step 5: Read seen hashes from Google Sheets ───────────────────────
    logger.info("Step 5 — Reading seen hashes from Google Sheets …")
    seen_hashes = read_seen_hashes(SHEET_ID)

    # ── Step 6: Filter to unseen jobs only ───────────────────────────────
    logger.info("Step 6 — Filtering unseen jobs …")
    new_jobs = [j for j in normalized if j["job_hash"] not in seen_hashes]
    logger.info(f"         → {len(new_jobs)} new (unseen) jobs")

    if not new_jobs:
        logger.info("No new jobs this cycle.")
        notify_no_new_jobs()
        return

    # ── Step 7+8: AI bulk scoring ─────────────────────────────────────────
    logger.info(f"Step 7+8 — AI scoring {len(new_jobs)} jobs …")
    kept_jobs = score_jobs(new_jobs)
    logger.info(f"           → {len(kept_jobs)} jobs kept after AI scoring")

    if not kept_jobs:
        logger.info("No jobs passed AI scoring.")
        notify_no_new_jobs()
        return

    # ── Step 9: Download master resume ───────────────────────────────────
    logger.info("Step 9 — Fetching master resume …")
    master_resume = download_resume(RESUME_FILE_ID) or load_local_resume()
    if not master_resume:
        logger.error("Could not load master resume from Drive or local file. Aborting.")
        notify_error("Could not load master_resume.json from Drive or local data/")
        return

    # ── Step 10: Per-job loop ─────────────────────────────────────────────
    logger.info(f"Step 10 — Processing {len(kept_jobs)} kept jobs …")
    cl_dir = Path("cover_letters")
    cl_dir.mkdir(exist_ok=True)

    rows_written = 0
    for i, job in enumerate(kept_jobs, 1):
        title   = job.get("title", "?")
        company = job.get("company", "?")
        score   = job.get("ai_match_score", "?")
        logger.info(f"  [{i}/{len(kept_jobs)}] {title} @ {company}  (score={score})")

        # 10a. Extract JD structure
        jd_extract = extract_jd(job)
        time.sleep(1.5)   # rate-limit between LLM calls

        # 10b. Write cover letter
        cover_letter_md = write_cover_letter(job, jd_extract, master_resume)
        time.sleep(1.5)

        cl_link = ""
        if cover_letter_md:
            # Save locally
            filename = build_cover_letter_filename(job, jd_extract)
            local_path = cl_dir / filename
            local_path.write_text(cover_letter_md, encoding="utf-8")

            # 10c. Upload to Google Drive
            file_id, cl_link = upload_cover_letter(cover_letter_md, filename, DRIVE_FOLDER)

            # 10d. Share publicly
            if file_id:
                share_file_public(file_id)
        else:
            logger.warning(f"  Cover letter empty for job {job.get('job_id')}")

        # 10e. Append row to Google Sheets
        ok = append_job_row(
            sheet_id=SHEET_ID,
            job=job,
            jd_extract=jd_extract,
            cl_link=cl_link,
            today=TODAY,
        )
        if ok:
            rows_written += 1

        time.sleep(2.0)   # be gentle on APIs between jobs

    # ── Step 11: Slack summary ────────────────────────────────────────────
    elapsed = (datetime.now() - start).seconds
    logger.info("=" * 60)
    logger.info(
        f"✅ Pipeline complete in {elapsed}s — "
        f"{rows_written}/{len(kept_jobs)} rows written to Sheet"
    )
    notify_summary(kept=rows_written, total_scraped=len(raw_jobs), new_jobs=len(new_jobs))


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        logger.exception("Pipeline crashed:")
        notify_error(str(e))
        sys.exit(1)
