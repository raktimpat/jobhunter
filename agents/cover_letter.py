"""agents/cover_letter.py — tailored cover letter writer"""
import json, logging, os, time
from datetime import datetime

logger = logging.getLogger(__name__)


def _system_prompt(today: str, company: str) -> str:
    return f"""Write a tailored, professional cover letter. 280–340 words.
Output ONLY clean Markdown — no code fences, no preamble.

You receive MASTER_RESUME (JSON) and JD_EXTRACT (structured job data).

RULES:
- Reference 2–3 specific verifiable achievements from MASTER_RESUME that
  address the JD's top requirements. Use exact metrics from the resume.
- If JD_EXTRACT.hiring_manager_name is not empty, address them by name.
  Otherwise: "Dear Hiring Team,"
- Name the company and role in the first sentence.
- Tone: confident, direct. No filler: "passionate about", "excited to leverage".
- Zero claims not grounded in MASTER_RESUME.
- Last sentence: single specific call to action.

FORMAT:
{today} · {company}

Dear [Name / Hiring Team],

[3 paragraphs]

Best regards,
Raktim Patar
raktimpatar101@gmail.com · (+91) 6003404209 · linkedin.com/in/rpat73"""


def _call(system: str, user: str) -> str:
    provider = os.getenv("AI_PROVIDER", "gemini").lower()
    if provider == "gemini":
        from agents._gemini import call_gemini
        return call_gemini(system, user, max_tokens=1024)
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


def write_cover_letter(job: dict, jd_extract: dict, master_resume: dict) -> str:
    today   = datetime.now().strftime("%B %-d, %Y")
    company = jd_extract.get("company") or job.get("company", "the company")
    role    = jd_extract.get("role_title") or job.get("title", "the role")

    user_prompt = (
        f"MASTER_RESUME:\n{json.dumps(master_resume)}\n\n"
        f"JD_EXTRACT:\n{json.dumps(jd_extract)}\n\n"
        f"TARGET ROLE: {role} at {company}"
    )

    raw = ""
    for attempt in range(3):
        try:
            raw = _call(_system_prompt(today, company), user_prompt)
            break
        except Exception as e:
            wait = 5 * (attempt + 1)
            logger.warning(f"[CoverLetter] Attempt {attempt+1} failed: {e}. Retry in {wait}s …")
            time.sleep(wait)
    else:
        logger.error("[CoverLetter] All retries exhausted.")
        return ""

    text = raw.strip()
    if text.startswith("`"):
        text = text.split("\n", 1)[-1].rstrip("`").strip()
    return text
