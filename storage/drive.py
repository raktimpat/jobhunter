"""
storage/drive.py
────────────────
Google Drive integration using a Service Account.
Mirrors the three Drive nodes in the n8n workflow:
  - Download file  → downloads master_resume.json
  - Upload file    → uploads cover letter .md to the cover_letters folder
  - Share file     → makes the uploaded file publicly readable
"""

import io
import logging
import os
from typing import Optional, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
]


def _get_service():
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "google_credentials.json")
    credentials = service_account.Credentials.from_service_account_file(
        creds_path, scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def download_resume(file_id: str) -> Optional[dict]:
    """
    Download and parse master_resume.json from Google Drive.
    Returns the parsed dict, or None on failure.
    """
    import json
    service = _get_service()
    try:
        request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buf.seek(0)
        data = json.loads(buf.read().decode("utf-8"))
        logger.info(f"[Drive] Downloaded master_resume.json ({file_id})")
        return data
    except Exception as e:
        logger.error(f"[Drive] Failed to download resume: {e}")
        return None


def upload_cover_letter(
    markdown_content: str,
    filename: str,
    folder_id: str,
) -> Tuple[str, str]:
    """
    Upload a cover letter Markdown file to Google Drive.

    :param markdown_content: The cover letter text (Markdown)
    :param filename: e.g. "CL_Cohere_ML_Engineer_2026-06-15.md"
    :param folder_id: Google Drive folder ID (cover_letters folder)
    :returns: (file_id, web_view_link) — the uploaded file's ID and shareable link
    """
    service = _get_service()
    file_metadata = {
        "name": filename,
        "parents": [folder_id],
        "mimeType": "text/markdown",
    }
    media = MediaIoBaseUpload(
        io.BytesIO(markdown_content.encode("utf-8")),
        mimetype="text/markdown",
        resumable=False,
    )
    try:
        file = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id,webViewLink")
            .execute()
        )
        file_id = file.get("id", "")
        link = file.get("webViewLink", "")
        logger.info(f"[Drive] Uploaded {filename} → {link}")
        return file_id, link
    except HttpError as e:
        logger.error(f"[Drive] Upload failed: {e}")
        return "", ""


def share_file_public(file_id: str) -> bool:
    """
    Make a Drive file publicly readable (anyone with the link).
    Mirrors the n8n 'Share file' node.
    """
    service = _get_service()
    try:
        service.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"},
        ).execute()
        logger.info(f"[Drive] File {file_id} shared publicly.")
        return True
    except HttpError as e:
        logger.error(f"[Drive] Share failed: {e}")
        return False


def build_cover_letter_filename(job: dict, jd_extract: dict) -> str:
    """Generate a clean filename for the cover letter."""
    import re
    company = jd_extract.get("company") or job.get("company", "Unknown")
    role = jd_extract.get("role_title") or job.get("title", "Role")
    from datetime import date
    today = date.today().isoformat()
    # Sanitize: keep only alphanumerics, spaces, hyphens
    clean = re.sub(r"[^a-zA-Z0-9 \-]", "", f"{company} {role}")
    clean = re.sub(r"\s+", "_", clean.strip())[:60]
    return f"CL_{clean}_{today}.md"
