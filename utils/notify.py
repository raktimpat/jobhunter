"""
utils/notify.py
───────────────
Slack notification helper. Mirrors the two Slack nodes in the n8n workflow:
  - "Send a message" (no new jobs)
  - Slack summary after processing

If SLACK_BOT_TOKEN or SLACK_CHANNEL_ID are not set, notifications are silently skipped.
"""

import os
import json
import logging
import requests

logger = logging.getLogger(__name__)


def _post(text: str) -> bool:
    token = os.getenv("SLACK_BOT_TOKEN", "").strip()
    channel = os.getenv("SLACK_CHANNEL_ID", "").strip()

    if not token or not channel:
        logger.info("[Slack] Not configured — skipping notification.")
        return False

    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=json.dumps({"channel": channel, "text": text}),
        timeout=10,
    )
    data = resp.json()
    if not data.get("ok"):
        logger.warning(f"[Slack] Post failed: {data.get('error')}")
        return False
    return True


def notify_no_new_jobs() -> None:
    """Mirrors the n8n 'Send a message' node when no jobs pass the relevance filter."""
    _post(
        "ℹ️ Job Aggregator: ran but no jobs passed the relevance filter this cycle. "
        "Consider checking the search URLs in config/search_targets.py."
    )


def notify_summary(kept: int, total_scraped: int, new_jobs: int) -> None:
    """Summary notification after a successful pipeline run."""
    _post(
        f"✅ Job Aggregator complete:\n"
        f"  • Scraped: {total_scraped} jobs\n"
        f"  • New (unseen): {new_jobs}\n"
        f"  • Kept after AI scoring: {kept}\n"
        f"  • Cover letters generated and added to Sheet ✓"
    )


def notify_error(error: str) -> None:
    """Alert on pipeline failure."""
    _post(f"❌ Job Aggregator ERROR:\n```{error[:500]}```")
