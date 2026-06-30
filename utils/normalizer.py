"""
utils/normalizer.py
───────────────────
Normalizes raw LinkedIn job data into the flat dict schema used throughout
the pipeline. Mirrors the n8n `normalize_fields` Code node exactly.
"""

from typing import Any, Dict, Optional
import logging


logger = logging.getLogger()


def normalize_job(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convert a raw scraped LinkedIn job dict into the normalized schema.

    Returns None if the job is missing a title or description (incomplete).
    """
    logger.info("Raw file for normalization:----- %s ", raw)
    title = (raw.get("jobTitle") or "").strip()
    description = (raw.get("jobDescription") or "").strip()

    if not title or not description:
        return None  # skip incomplete results

    # salaryInfo is a list in the scraped schema
    salary_raw = raw.get("salaryInfo", [])
    salary = ", ".join(salary_raw) if isinstance(salary_raw, list) else str(salary_raw)

    matched = raw.get("matchedKeywords", [])
    unmatched = raw.get("unmatchedKeywords", [])

    return {
        "job_id":              raw.get("jobId", ""),
        "title":               title,
        "company":             (raw.get("companyName") or "").strip(),
        "location":            (raw.get("location") or "").strip(),
        "description":         description,
        "url":                 (raw.get("jobUrl") or "").strip(),
        "apply_url":           (raw.get("applyUrl") or "").strip(),
        "apply_type":          raw.get("applyType", ""),          # EXTERNAL or EASY_APPLY
        "salary_info":         salary,
        "posted_at":           raw.get("publishedAt", ""),
        "contract_type":       raw.get("contractType", ""),
        "experience_level":    raw.get("experienceLevel", ""),
        "applications_count":  str(raw.get("applicationsCount", "")),
        "keyword_match_score": raw.get("keywordMatchScorePercentage", 0),
        "matched_keywords":    ", ".join(matched) if isinstance(matched, list) else "",
        "unmatched_keywords":  ", ".join(unmatched) if isinstance(unmatched, list) else "",
        "hiring_manager_name": raw.get("" \
        "", ""),
        "hiring_manager_url":  raw.get("posterProfileUrl", ""),
        "company_size":        raw.get("companyEmployeeCountRange", ""),
        "company_industry":    raw.get("companyIndustry", ""),
        "company_url":         raw.get("companyUrl", ""),
        "source":              "linkedin",
    }
