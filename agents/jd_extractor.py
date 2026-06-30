"""agents/jd_extractor.py — structured JD extraction"""
import json, logging, os, time
from typing import Dict

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Extract structured data from a LinkedIn job posting.
RULES: extract only what is explicitly present. Never infer or fabricate.
Defaults: string=""  number=0  boolean=false  array=[]
work_mode: infer from text ("remote","hybrid","on-site"). If unclear: "unspecified".
Output ONLY raw JSON — no markdown fences, no explanation.
Schema:
{"role_title":"","company":"","location":"","work_mode":"",
 "required_years_experience":0,"required_skills":[],
 "key_responsibilities":"","contact_email":"",
 "whatsapp_number":"","easy_apply_url":""}"""


def _call(user_prompt: str) -> str:
    provider = os.getenv("AI_PROVIDER", "gemini").lower()
    if provider == "gemini":
        from agents._gemini import call_gemini
        return call_gemini(SYSTEM_PROMPT, user_prompt, max_tokens=1024)
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return msg.content[0].text


def extract_jd(job: dict) -> dict:
    user_prompt = (
        f"Job Title: {job.get('title','')}\n"
        f"Company: {job.get('company','')}\n"
        f"Location: {job.get('location','')}\n"
        f"Experience Level: {job.get('experience_level','')}\n"
        f"Contract Type: {job.get('contract_type','')}\n\n"
        f"Full Job Description:\n{job.get('description','')}"
    )
    raw = ""
    for attempt in range(3):
        try:
            raw = _call(user_prompt)
            break
        except Exception as e:
            wait = 5 * (attempt + 1)
            logger.warning(f"[JDExtractor] Attempt {attempt+1} failed: {e}. Retry in {wait}s …")
            time.sleep(wait)
    else:
        logger.error("[JDExtractor] All retries exhausted.")
        return {}

    try:
        text = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        extracted = json.loads(text)
    except Exception as e:
        logger.error(f"[JDExtractor] Parse error: {e}")
        return {}

    skills = extracted.get("required_skills", [])
    extracted["required_skills_str"] = ", ".join(skills) if isinstance(skills, list) else str(skills)
    years = extracted.get("required_years_experience", 0)
    extracted["required_years_experience"] = years if years else ""
    return extracted
