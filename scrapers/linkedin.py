"""
scrapers/linkedin.py
────────────────────
LinkedIn job scraper — resilient multi-strategy approach.

Strategy 1 (primary): Guest API endpoint with JSON-embedded data
  POST https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
  Returns HTML fragments. We look for job IDs in multiple ways.

Strategy 2 (fallback): Public search page
  GET  https://www.linkedin.com/jobs/search/?keywords=...&location=...
  Parses <code> tags that contain embedded JSON job data.

Both strategies use BeautifulSoup. When LinkedIn returns a challenge/auth
page instead of jobs, we detect it early and log clearly.

Debug: set SCRAPER_DEBUG=1 in .env to dump raw responses to logs/debug_*.html
"""

import json
import logging
import os
import re
import time
import random
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse, parse_qs, urlencode, quote_plus

import requests
from bs4 import BeautifulSoup

from config.search_targets import RESUME_KEYWORDS, EXCLUDE_TITLE_KEYWORDS, EXCLUDE_COMPANIES

logger = logging.getLogger(__name__)

GUEST_API   = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_API  = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{}"
SEARCH_PAGE = "https://www.linkedin.com/jobs/search/"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]


# ── Session ───────────────────────────────────────────────────────────────

def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    return s


def _sleep(lo: float = 2.5, hi: float = 6.0) -> None:
    time.sleep(random.uniform(lo, hi))


# ── Challenge / block detection ───────────────────────────────────────────

BLOCK_SIGNALS = [
    "join now to see",
    "authwall",
    "sign in",
    "join linkedin",
    "verify you're human",
    "please complete the security check",
    "access to this page has been denied",
    "linkedin.com/checkpoint",
    "let's do a quick security check",
]

def _block_reason(html: str) -> Optional[str]:
    """
    Returns the matched LinkedIn block signal.
    Returns None if the page appears to be valid.
    """

    low = html.lower()

    for signal in BLOCK_SIGNALS:
        if signal.lower() in low:
            return signal

    return None

def _is_blocked(html: str) -> bool:
    """Return True if LinkedIn returned a challenge/auth wall instead of jobs."""
    low = html.lower()
    return any(signal in low for signal in BLOCK_SIGNALS)


def _debug_dump(html: str, label: str) -> None:
    if os.getenv("SCRAPER_DEBUG", "0") != "1":
        return
    Path("logs").mkdir(exist_ok=True)
    fname = f"logs/debug_{label}_{int(time.time())}.html"
    Path(fname).write_text(html, encoding="utf-8")
    logger.info(f"  [DEBUG] Dumped to {fname}")


# ── Keyword matching ──────────────────────────────────────────────────────

def _match_keywords(text: str, keywords: List[dict]) -> Tuple[List[str], List[str], int]:
    text_lower = text.lower()
    matched, unmatched = [], []
    for entry in keywords:
        kw    = entry["keyword"]
        terms = [kw] + entry.get("aliases", [])
        found = any(
            re.search(r"\b" + re.escape(t.lower()) + r"\b", text_lower)
            for t in terms
        )
        (matched if found else unmatched).append(kw)
    score = round(len(matched) / len(keywords) * 100) if keywords else 0
    return matched, unmatched, score


def _should_exclude(title: str, company: str) -> bool:
    for kw in EXCLUDE_TITLE_KEYWORDS:
        if re.search(r"\b" + re.escape(kw.lower()) + r"\b", title.lower()):
            return True
    for exc in EXCLUDE_COMPANIES:
        if exc.lower() in company.lower():
            return True
    return False


# ── HTTP fetch ────────────────────────────────────────────────────────────

def _get(session: requests.Session, url: str, params: dict = None,
         extra_headers: dict = None) -> Optional[str]:
    headers = {}
    if extra_headers:
        headers.update(extra_headers)

    MAX_RETRIES = 3
    for attempt in range(MAX_RETRIES):
        try:
            _sleep(2.0 + attempt, 5.0 + attempt * 2)
            resp = session.get(url, params=params, headers=headers, timeout=20)

            if resp.status_code == 200:
                return resp.text
            if resp.status_code == 429:
                wait = 60 * (attempt + 1)
                logger.warning(f"  Rate limited (429) — waiting {wait}s …")
                time.sleep(wait)
                session.headers["User-Agent"] = random.choice(USER_AGENTS)
                continue
            if resp.status_code in (403, 999):
                logger.warning(f"  Blocked (HTTP {resp.status_code}) — LinkedIn is rejecting the request.")
                return None
            logger.warning(f"  HTTP {resp.status_code} — {url[:80]}")
            return None

        except requests.exceptions.Timeout:
            logger.warning(f"  Timeout (attempt {attempt+1}/3)")
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"  Connection error: {e}")
            return None

    return None


# ═══════════════════════════════════════════════════════════════════════════
# Strategy 1: Guest API (returns HTML fragment with <li> job cards)
# ═══════════════════════════════════════════════════════════════════════════

def _extract_job_ids_from_fragment(soup: BeautifulSoup) -> List[str]:
    """
    Extract job IDs from the guest API HTML fragment.
    LinkedIn embeds them in multiple ways — we try all of them.
    """
    ids = []

    # Method A: data-entity-urn on <li> or any tag
    for tag in soup.find_all(attrs={"data-entity-urn": True}):
        urn = tag.get("data-entity-urn", "")
        m = re.search(r":(\d{8,})", urn)
        if m:
            ids.append(m.group(1))

    # Method B: job URLs in <a> href
    for a in soup.find_all("a", href=True):
        m = re.search(r"/jobs/view/(\d{8,})", a["href"])
        if m and m.group(1) not in ids:
            ids.append(m.group(1))

    # Method C: data-job-id attribute
    for tag in soup.find_all(attrs={"data-job-id": True}):
        jid = tag.get("data-job-id", "").strip()
        if jid.isdigit() and jid not in ids:
            ids.append(jid)

    # Method D: currentJobId in any href/onclick
    for tag in soup.find_all(attrs={"data-occludable-job-id": True}):
        jid = tag.get("data-occludable-job-id", "").strip()
        if jid.isdigit() and jid not in ids:
            ids.append(jid)

    return list(dict.fromkeys(ids))  # deduplicate, preserve order


def _parse_card_meta(soup: BeautifulSoup, job_id: str) -> dict:
    """
    Extract title, company, location from an <li> card containing job_id.
    Tries multiple selectors because LinkedIn class names change frequently.
    """
    # Find the card that contains this job ID
    card = None
    for li in soup.find_all("li"):
        if job_id in str(li):
            card = li
            break
    if not card:
        card = soup  # fallback: search whole fragment

    title = ""
    for sel in [
        {"class": re.compile(r"base-search-card__title")},
        {"class": re.compile(r"job-search-card__title")},
        "h3", "h4",
    ]:
        tag = card.find(True, sel) if isinstance(sel, dict) else card.find(sel)
        if tag:
            title = tag.get_text(strip=True)
            if title:
                break

    company = ""
    for sel in [
        {"class": re.compile(r"base-search-card__subtitle")},
        {"class": re.compile(r"hidden-nested-link")},
        {"class": re.compile(r"job-search-card__company-name")},
    ]:
        tag = card.find(True, sel)
        if tag:
            company = tag.get_text(strip=True)
            if company:
                break

    location = ""
    for sel in [
        {"class": re.compile(r"job-search-card__location")},
        {"class": re.compile(r"base-search-card__metadata")},
    ]:
        tag = card.find(True, sel)
        if tag:
            location = tag.get_text(strip=True)
            if location:
                break

    time_tag     = card.find("time")
    published_at = time_tag.get("datetime", "") if time_tag else ""
    posted_time  = time_tag.get_text(strip=True) if time_tag else ""

    return {
        "jobId":       job_id,
        "jobTitle":    title,
        "companyName": company,
        "location":    location,
        "publishedAt": published_at,
        "postedTime":  posted_time,
        "jobUrl":      f"https://www.linkedin.com/jobs/view/{job_id}/",
        "applyUrl":    f"https://www.linkedin.com/jobs/view/{job_id}/",
        "applyType":   "EXTERNAL",
        "salaryInfo":  [],
    }


def _scrape_via_guest_api(session: requests.Session, base_params: dict,
                           max_per_url: int, seen_ids: set) -> List[dict]:
    jobs = []
    keyword  = base_params.get("keywords", "?")
    location = base_params.get("location", base_params.get("geoId", "?"))

    for page in range(0, 20):
        if len(jobs) >= max_per_url:
            break

        params   = {**base_params, "start": page * 10}
        fragment = _get(session, GUEST_API, params=params)

        if not fragment:
            logger.info(f"  [guest-api] No response at page {page}")
            break

        if _is_blocked(fragment):
            logger.warning(
                f"  [guest-api] LinkedIn returned auth wall for '{keyword}' in '{location}'. "
                "This is normal — LinkedIn blocks scraping intermittently. "
                "Try again in 10–30 minutes, or use a VPN."
            )
            _debug_dump(fragment, f"blocked_{keyword[:20]}")
            break

        soup = BeautifulSoup(fragment, "html.parser")
        job_ids = _extract_job_ids_from_fragment(soup)

        logger.info(
            f"  [guest-api] Page {page}: {len(job_ids)} IDs from "
            f"{len(fragment)} bytes | '{keyword}' in '{location}'"
        )

        if not job_ids:
            _debug_dump(fragment, f"noids_page{page}_{keyword[:15]}")
            break

        new_this_page = 0
        for job_id in job_ids:
            if job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            card = _parse_card_meta(soup, job_id)
            if _should_exclude(card["jobTitle"], card["companyName"]):
                continue

            detail_html = _get(session, DETAIL_API.format(job_id))
            if detail_html:
                card.update(_parse_job_detail(detail_html))
            else:
                logger.warning(
                    f"Failed to parse detail page for {job_id}"
                )

            desc = card.get("jobDescription", "")
            matched, unmatched, score = _match_keywords(desc, RESUME_KEYWORDS)
            card["matchedKeywords"]             = matched
            card["unmatchedKeywords"]           = unmatched
            card["keywordMatchScorePercentage"] = score

            jobs.append(card)
            new_this_page += 1
            logger.info(
                f"    [{len(jobs)}] {card['jobTitle']!r} @ {card['companyName']!r} "
                f"| kw={score}% | {card['location']}"
            )

        if new_this_page == 0:
            break

    return jobs


# ═══════════════════════════════════════════════════════════════════════════
# Strategy 2: Public search page (embedded JSON in <code> tags)
# ═══════════════════════════════════════════════════════════════════════════

def _scrape_via_search_page(session: requests.Session, keywords: str,
                             location: str, seen_ids: set,
                             max_per_url: int) -> List[dict]:
    """
    Scrape LinkedIn's public /jobs/search page.
    LinkedIn embeds job data as JSON inside <code> tags on this page.
    """
    jobs = []

    for page in range(0, 10):
        if len(jobs) >= max_per_url:
            break

        params = {
            "keywords": keywords,
            "location": location,
            "start": page * 25,
            "f_TPR": "r604800",
        }

        # Pretend we're a real browser visiting the search page
        html = _get(session, SEARCH_PAGE, params=params, extra_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.linkedin.com/",
        })

        if not html:
            break

        if _is_blocked(html):
            logger.warning(f"  [search-page] Auth wall for '{keywords}' in '{location}'")
            _debug_dump(html, f"blocked_search_{keywords[:15]}")
            break

        soup  = BeautifulSoup(html, "html.parser")
        cards = _parse_search_page_cards(soup)

        logger.info(f"  [search-page] Page {page}: {len(cards)} cards for '{keywords}' in '{location}'")

        if not cards:
            # Try to extract IDs from JSON embedded in <code> tags
            cards = _extract_from_code_tags(html)
            logger.info(f"  [search-page] Fallback code-tag extraction: {len(cards)} cards")

        if not cards:
            _debug_dump(html, f"nocards_search_{keywords[:15]}")
            break

        new_this_page = 0
        for card in cards:
            job_id = card.get("jobId", "")
            if not job_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            if _should_exclude(card.get("jobTitle",""), card.get("companyName","")):
                continue

            # Fetch detail if we don't already have description
            if not card.get("jobDescription"):
                detail_html = _get(session, DETAIL_API.format(job_id))
                if detail_html:
                    card.update(_parse_job_detail(detail_html))
                else:
                    logger.warning(
                        f"Failed to parse detail page for {job_id}"
                    )

            desc = card.get("jobDescription", "")
            matched, unmatched, score = _match_keywords(desc, RESUME_KEYWORDS)
            card["matchedKeywords"]             = matched
            card["unmatchedKeywords"]           = unmatched
            card["keywordMatchScorePercentage"] = score

            jobs.append(card)
            new_this_page += 1
            logger.info(
                f"    [{len(jobs)}] {card['jobTitle']!r} @ {card['companyName']!r} "
                f"| kw={score}% | {card.get('location','')}"
            )

        if new_this_page == 0:
            break

    return jobs


def _parse_search_page_cards(soup: BeautifulSoup) -> List[dict]:
    """Parse job cards from the public search results page HTML."""
    cards = []

    # LinkedIn renders jobs in <ul class="jobs-search__results-list"> or similar
    for li in soup.find_all("li"):
        # Must have a job URL link
        link = li.find("a", href=re.compile(r"/jobs/view/\d+"))
        if not link:
            continue

        m = re.search(r"/jobs/view/(\d+)", link["href"])
        if not m:
            continue
        job_id = m.group(1)

        title_tag = (
            li.find(class_=re.compile(r"base-search-card__title|job-search-card__title")) or
            li.find("h3") or li.find("h4")
        )
        title = title_tag.get_text(strip=True) if title_tag else link.get_text(strip=True)

        company_tag = li.find(class_=re.compile(r"base-search-card__subtitle|company-name"))
        company = company_tag.get_text(strip=True) if company_tag else ""

        loc_tag = li.find(class_=re.compile(r"job-search-card__location|base-search-card__metadata"))
        location = loc_tag.get_text(strip=True) if loc_tag else ""

        time_tag = li.find("time")
        published_at = time_tag.get("datetime", "") if time_tag else ""

        if not title:
            continue

        cards.append({
            "jobId":       job_id,
            "jobTitle":    title,
            "companyName": company,
            "location":    location,
            "publishedAt": published_at,
            "jobUrl":      f"https://www.linkedin.com/jobs/view/{job_id}/",
            "applyUrl":    f"https://www.linkedin.com/jobs/view/{job_id}/",
            "applyType":   "EXTERNAL",
            "salaryInfo":  [],
        })

    return cards


def _extract_from_code_tags(html: str) -> List[dict]:
    """
    LinkedIn sometimes embeds all job data as JSON inside <code> tags.
    This is a robust fallback that doesn't depend on any class names.
    """
    cards = []
    soup = BeautifulSoup(html, "html.parser")

    for code_tag in soup.find_all("code"):
        text = code_tag.get_text()
        if '"jobPosting"' not in text and '"entityUrn"' not in text:
            continue
        try:
            data = json.loads(text)
        except Exception:
            # Try to find JSON objects inside the text
            for m in re.finditer(r'\{[^{}]{100,}\}', text):
                try:
                    data = json.loads(m.group())
                    cards.extend(_extract_jobs_from_json(data))
                except Exception:
                    pass
            continue
        cards.extend(_extract_jobs_from_json(data))

    # Also scan all script tags for job data
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.get_text())
            if isinstance(data, dict) and data.get("@type") in ("JobPosting", "ItemList"):
                cards.extend(_extract_jobs_from_json(data))
        except Exception:
            pass

    return cards


def _extract_jobs_from_json(data: dict) -> List[dict]:
    """Recursively extract job postings from an arbitrary JSON blob."""
    cards = []

    def _walk(obj):
        if isinstance(obj, dict):
            # Check if this looks like a job posting
            urn = obj.get("entityUrn", "") or obj.get("jobPostingUrn", "")
            jid_m = re.search(r":(\d{8,})", urn)
            if jid_m:
                title = (
                    obj.get("title") or
                    obj.get("jobTitle") or
                    (obj.get("title", {}) or {}).get("text", "") if isinstance(obj.get("title"), dict) else ""
                )
                if title:
                    jid = jid_m.group(1)
                    cards.append({
                        "jobId":       jid,
                        "jobTitle":    str(title),
                        "companyName": str(obj.get("companyName", "") or obj.get("company", {}).get("name", "") if isinstance(obj.get("company"), dict) else obj.get("company", "")),
                        "location":    str(obj.get("formattedLocation", "") or obj.get("location", "")),
                        "publishedAt": str(obj.get("listedAt", "") or obj.get("postedAt", "")),
                        "jobUrl":      f"https://www.linkedin.com/jobs/view/{jid}/",
                        "applyUrl":    f"https://www.linkedin.com/jobs/view/{jid}/",
                        "applyType":   "EXTERNAL",
                        "salaryInfo":  [],
                    })
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(data)
    return cards


# ═══════════════════════════════════════════════════════════════════════════
# Job detail parser (shared by both strategies)
# ═══════════════════════════════════════════════════════════════════════════

import re
from bs4 import BeautifulSoup


def _text(node):
    return node.get_text(" ", strip=True) if node else ""


def _parse_job_detail(html_fragment: str) -> dict:
    soup = BeautifulSoup(html_fragment, "html.parser")

    result = {}

    title = soup.select_one(".top-card-layout__title")
    result["title"] = _text(title)

    company = soup.select_one(".topcard__org-name-link")
    result["companyName"] = _text(company)
    result["companyUrl"] = company.get("href", "") if company else ""

    logo = soup.select_one("img.artdeco-entity-image")
    result["companyLogo"] = (
        logo.get("data-delayed-url")
        or logo.get("src")
        or ""
    ) if logo else ""

    job_link = soup.select_one("a.topcard__link")
    result["jobUrl"] = job_link.get("href", "") if job_link else ""

    location = ""
    for span in soup.select(".topcard__flavor"):
        txt = _text(span)
        if "," in txt:
            location = txt
            break
    result["location"] = location
    posted = soup.select_one(".posted-time-ago__text")
    result["postedTime"] = _text(posted)

    # Applicants
    applicants = soup.select_one(".num-applicants__caption")
    if applicants:
        result["applicationsCount"] = _text(applicants)
    else:
        apps = soup.find(string=re.compile(r"(over\s+)?[\d,]+\+?\s+applicants?", re.I))
        result["applicationsCount"] = apps.strip() if apps else ""

    # Description
    desc = (
        soup.select_one(".show-more-less-html__markup")
        or soup.select_one(".description__text")
        or soup.find(class_=re.compile(r"jobs-description"))
    )
    result["jobDescriptionHtml"] = str(desc) if desc else ""
    result["jobDescription"] = (
        desc.get_text(" ", strip=True)
        if desc else ""
    )
    if desc is None:
        return None

    result["contractType"] = ""
    result["experienceLevel"] = ""
    result["jobFunction"] = ""
    result["industry"] = ""
    for item in soup.select(".description__job-criteria-item"):
        h = item.find("h3")
        v = item.find(class_=re.compile(r"description__job-criteria-text"))
        if not h or not v:
            continue
        header = _text(h).lower()
        value = _text(v)
        if "employment" in header:
            result["contractType"] = value
        elif "seniority" in header:
            result["experienceLevel"] = value
        elif "job function" in header:
            result["jobFunction"] = value
        elif "industry" in header:
            result["industry"] = value

    apply_button = soup.select_one("button.apply-button")
    if apply_button and "easy" in apply_button.get_text(" ", strip=True).lower():
        result["applyType"] = "EASY_APPLY"
    else:
        result["applyType"] = "EXTERNAL"
    salary_matches = re.findall(
        r"(?:\$|£|€|₹)\s?[\d,]+(?:\s*-\s*(?:\$|£|€|₹)?\s?[\d,]+)?",
        soup.get_text(" ", strip=True)
    )
    result["salaryInfo"] = salary_matches
    ref = soup.find("code", id="referenceId")
    result["referenceId"] = _text(ref)

    # ── Hiring Manager / Recruiter ─────────────────────────────────────────
    result["hiringManagerName"] = ""
    result["hiringManagerTitle"] = ""
    result["hiringManagerLinkedin"] = ""
    result["hiringManagerEmail"] = ""
    result["hiringManagerPhone"] = ""

    page_text = soup.get_text("\n", strip=True)

    # Email
    EMAIL_RE = re.compile(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
    )
    emails = EMAIL_RE.findall(page_text)
    if emails:
        result["hiringManagerEmail"] = emails[0]

    # Phone / WhatsApp (only if explicitly mentioned)
    CONTACT_LABEL_RE = re.compile(
        r"(whatsapp|mobile|phone|call|contact\s*number|reach\s*me|reach\s*out)",
        re.I,
    )
    PHONE_RE = re.compile(
        r"(?:\+\d{1,3}[\s\-]?)?"
        r"(?:\(?\d{2,5}\)?[\s\-]?)?"
        r"\d{3,4}[\s\-]?\d{4}"
    )
    for line in page_text.splitlines():
        if CONTACT_LABEL_RE.search(line):
            phone = PHONE_RE.search(line)
            if phone:
                result["hiringManagerPhone"] = phone.group(0)
                break

    # Recruiter / Hiring Manager LinkedIn Profile
    profiles = soup.find_all(
        "a",
        href=re.compile(r"/in/|linkedin\.com/in/")
    )
    for profile in profiles:
        href = profile.get("href", "")
        if href.startswith("/"):
            href = "https://www.linkedin.com" + href
        name = profile.get_text(" ", strip=True)
        # Ignore empty or obviously invalid names
        if not (1 <= len(name.split()) <= 5):
            continue
        result["hiringManagerName"] = name
        result["hiringManagerLinkedin"] = href
        # Try to infer title from nearby text
        parent = profile.find_parent()

        if parent:
            lines = [
                x.strip()
                for x in parent.get_text("\n", strip=True).split("\n")
                if x.strip()
            ]
            for line in lines:
                if line == name:
                    continue
                if any(
                    keyword in line.lower()
                    for keyword in (
                        "recruit",
                        "talent",
                        "acquisition",
                        "hr",
                        "human resources",
                        "manager",
                        "director",
                        "lead",
                        "partner",
                    )
                ):
                    result["hiringManagerTitle"] = line
                    break

        break

    # Fallback: "Meet the hiring team"
    if not result["hiringManagerName"]:
        hiring = soup.find(
            string=re.compile(r"meet the hiring team", re.I)
        )
        if hiring:
            section = hiring.find_parent()
            if section:
                profile = section.find(
                    "a",
                    href=re.compile(r"/in/")
                )
                if profile:
                    href = profile.get("href", "")
                    if href.startswith("/"):
                        href = "https://www.linkedin.com" + href
                    result["hiringManagerName"] = profile.get_text(
                        " ",
                        strip=True,
                    )
                    result["hiringManagerLinkedin"] = href

    # Fallback: "Posted by"
    if not result["hiringManagerName"]:
        posted = soup.find(
            string=re.compile(r"posted by", re.I)
        )
        if posted:
            section = posted.find_parent()
            if section:
                profile = section.find(
                    "a",
                    href=re.compile(r"/in/")
                )
                if profile:
                    href = profile.get("href", "")
                    if href.startswith("/"):
                        href = "https://www.linkedin.com" + href
                    result["hiringManagerName"] = profile.get_text(
                        " ",
                        strip=True,
                    )
                    result["hiringManagerLinkedin"] = href
    return result


# ═══════════════════════════════════════════════════════════════════════════
# URL → params helper
# ═══════════════════════════════════════════════════════════════════════════

def _url_to_params(linkedin_url: str) -> dict:
    parsed = urlparse(linkedin_url)
    return {k: v[0] for k, v in parse_qs(parsed.query).items()}


# ═══════════════════════════════════════════════════════════════════════════
# Public entry point
# ═══════════════════════════════════════════════════════════════════════════

def scrape_jobs(search_urls: List[str], max_items: int = 200) -> List[dict]:
    """
    Scrape LinkedIn jobs. Tries guest API first, falls back to search page.
    Returns jobs in Apify-compatible schema with keyword matching scores.
    """
    session  = _make_session()
    seen_ids: set  = set()
    all_jobs: List[dict] = []

    # Warm up the session with a visit to linkedin.com first (sets cookies)
    logger.info("Warming up session …")
    warmup = _get(session, "https://www.linkedin.com/jobs/", extra_headers={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    })
    if warmup:
        logger.info(f"  Session warmed up ({len(warmup)} bytes)")
    _sleep(2.0, 4.0)

    for url in search_urls:
        if len(all_jobs) >= max_items:
            break

        base_params = _url_to_params(url)
        keywords    = base_params.get("keywords", "")
        location    = base_params.get("location", "")
        max_per_url = min(50, max_items - len(all_jobs))

        logger.info(f"Scraping: '{keywords}' in '{location}'")

        # ── Strategy 1: Guest API ─────────────────────────────────────────
        jobs = _scrape_via_guest_api(session, base_params, max_per_url, seen_ids)

        # ── Strategy 2: Search page (if guest API returned nothing) ───────
        if not jobs and keywords and location:
            logger.info(f"  Guest API returned 0 — trying search page fallback …")
            jobs = _scrape_via_search_page(
                session, keywords, location, seen_ids, max_per_url
            )

        all_jobs.extend(jobs)
        logger.info(f"  → {len(jobs)} jobs from this URL (total: {len(all_jobs)})")

        # Rotate user-agent between URLs
        session.headers["User-Agent"] = random.choice(USER_AGENTS)
        _sleep(3.0, 7.0)

    logger.info(f"Scraping complete — {len(all_jobs)} jobs collected.")
    return all_jobs
