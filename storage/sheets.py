"""
storage/sheets.py
─────────────────
Google Sheets integration using a Service Account (no OAuth pop-up).
Mirrors the three Sheets nodes in the n8n workflow:
  - read_seen_hashes  → reads existing Job Hash column to detect duplicates
  - Append row in sheet1 → appends new job rows to the Applications tab
"""

import logging
import os
from typing import Any, Set

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# ── Column order in the Applications sheet ───────────────────────────────
# Must match the column headers in your Google Sheet exactly.
COLUMN_ORDER = [
    "Date Found",
    "Job ID",
    "Job Title ",        # note: trailing space matches the n8n schema
    "Company ",          # note: trailing space
    "Location",
    "Work Mode",
    "Contract Type",
    "Experience Level",
    "Source",
    "Job URL",
    "Apply URL",
    "Apply Type",
    "Salary Info",
    "Application Count",
    "Keyword Match Score",
    "Matched Keywords",
    "Unmatched Keywords",
    "AI Match Score",
    "AI Match Reason",
    "JD Summary",
    "Required Skills",
    "Hiring Manager Name",
    "Hiring Manager Linkedin",
    "Contact Email ",    # note: trailing space
    "WhatsApp Number",
    "Easy Apply URL",
    "Cover Letter",
    "Application Method",
    "Outreach Status",
    "Job Hash",
]


def _get_service():
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "google_credentials.json")
    credentials = service_account.Credentials.from_service_account_file(
        creds_path, scopes=SCOPES
    )
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def read_seen_hashes(sheet_id: str, tab_name: str = "Applications") -> Set[str]:
    """
    Read all existing Job Hash values from the sheet.
    Returns a set of hash strings for O(1) lookup.
    """
    service = _get_service()
    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=sheet_id, range=f"{tab_name}!A:AZ")
            .execute()
        )
    except HttpError as e:
        logger.error(f"[Sheets] Failed to read seen hashes: {e}")
        return set()

    rows = result.get("values", [])
    if not rows:
        return set()

    # Find the "Job Hash" column index from the header row
    header = rows[0]
    try:
        hash_col = header.index("Job Hash")
    except ValueError:
        logger.warning("[Sheets] 'Job Hash' column not found — treating all jobs as new.")
        return set()

    hashes = set()
    for row in rows[1:]:
        if len(row) > hash_col:
            val = str(row[hash_col]).strip()
            if val:
                hashes.add(val)

    logger.info(f"[Sheets] Loaded {len(hashes)} seen job hashes.")
    return hashes


def append_job_row(
    sheet_id: str,
    job: dict,
    jd_extract: dict,
    cl_link: str,
    today: str,
    tab_name: str = "Applications",
) -> bool:
    """
    Append a single job row to the Applications sheet.
    Mirrors the n8n 'Append row in sheet1' node with all its mapped fields.
    """
    role_title = jd_extract.get("output", {}).get("role_title") or jd_extract.get("role_title", job.get("title", ""))
    company    = jd_extract.get("output", {}).get("company")    or jd_extract.get("company",    job.get("company", ""))
    location   = jd_extract.get("output", {}).get("location")   or jd_extract.get("location",   job.get("location", ""))
    work_mode  = jd_extract.get("output", {}).get("work_mode")  or jd_extract.get("work_mode",  "unspecified")

    row_data = {
        "Date Found":               today,
        "Job ID":                   job.get("job_id", ""),
        "Job Title ":               role_title,
        "Company ":                 company,
        "Location":                 location,
        "Work Mode":                work_mode,
        "Contract Type":            job.get("contract_type", ""),
        "Experience Level":         job.get("experience_level", ""),
        "Source":                   job.get("source", "linkedin"),
        "Job URL":                  job.get("url", ""),
        "Apply URL":                job.get("apply_url", ""),
        "Apply Type":               job.get("apply_type", ""),
        "Salary Info":              job.get("salary_info", ""),
        "Application Count":        job.get("applications_count", ""),
        "Keyword Match Score":      str(job.get("keyword_match_score", "")),
        "Matched Keywords":         job.get("matched_keywords", ""),
        "Unmatched Keywords":       job.get("unmatched_keywords", ""),
        "AI Match Score":           str(job.get("ai_match_score", "")),
        "AI Match Reason":          job.get("ai_match_reason", ""),
        "JD Summary":               jd_extract.get("key_responsibilities", ""),
        "Required Skills":          jd_extract.get("required_skills_str", ""),
        "Hiring Manager Name":      job.get("hiring_manager_name", ""),
        "Hiring Manager Linkedin":  job.get("hiring_manager_url", ""),
        "Contact Email ":           jd_extract.get("contact_email", ""),
        "WhatsApp Number":          jd_extract.get("whatsapp_number", ""),
        "Easy Apply URL":           job.get("url", "") if job.get("apply_type") == "EASY_APPLY" else "",
        "Cover Letter":             cl_link,
        "Application Method":       "pending",
        "Outreach Status":          "new",
        "Job Hash":                 job.get("job_hash", ""),
    }

    row_values = [row_data.get(col, "") for col in COLUMN_ORDER]

    service = _get_service()
    try:
        service.spreadsheets().values().append(
            spreadsheetId=sheet_id,
            range=f"{tab_name}!A:A",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": [row_values]},
        ).execute()
        logger.info(f"[Sheets] Appended: {job.get('title')} @ {job.get('company')}")
        return True
    except HttpError as e:
        logger.error(f"[Sheets] Append failed: {e}")
        return False


def ensure_header_row(sheet_id: str, tab_name: str = "Applications") -> None:
    """
    Write the header row if the sheet is empty.
    Safe to call on every run — it checks first.
    """
    service = _get_service()
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=f"{tab_name}!A1:A1")
        .execute()
    )
    if result.get("values"):
        return  # header already exists

    service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=f"{tab_name}!A1",
        valueInputOption="USER_ENTERED",
        body={"values": [COLUMN_ORDER]},
    ).execute()
    logger.info("[Sheets] Header row written.")
