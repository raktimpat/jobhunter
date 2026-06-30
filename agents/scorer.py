"""
agents/scorer.py  —  bulk AI job scorer
Supports AI_PROVIDER=gemini (google-genai SDK) or claude (anthropic SDK).
"""
import json, logging, os, time
from typing import List

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You score a batch of LinkedIn job listings for a specific candidate.

CANDIDATE PROFILE — Raktim Patar:
- Roles: AI Engineer / Data Scientist / Machine Learning Engineer / LLM Engineer
- Experience: 5+ years total (Oct 2020 to Jun 2026)
- Most recent: AI Engineer at Google Internal AI Tooling (XWF via Virtusa),
  Dec 2025–Jun 2026. Built multi-agent self-healing framework (Gemini LLMs),
  Locator RAG system (GCS, Cloud Spanner, Vertex AI), CL History RAG pipeline.
- Core skills: LLMs, RAG systems, multi-agent frameworks, Gemini/Vertex AI,
  GCP (Cloud Spanner, GCS), AWS (SageMaker, S3), Python, PyTorch, TensorFlow,
  FastAPI, Docker, Kubernetes, GitHub Actions, MLOps, computer vision, NLP,
  LangChain, SQL, Airflow
- Open to: Remote India, Hybrid/Onsite Bengaluru, Singapore, Dubai, Abu Dhabi,
  Sydney, Melbourne, Brisbane, Amsterdam, Rotterdam, Eindhoven
- NOT a fit for: pure Data Analyst, BI/Tableau-only, DevOps-only, mobile,
  frontend, backend-only, QA/test engineering

INPUT: JSON array — each item has: index, title, company, location,
experience_level, contract_type, matched_keywords, keyword_match_score,
description_preview.

Return a JSON object IN THIS EXACT FORMAT — no markdown fences, no extra text:
{"scored_jobs":[{"index":0,"decision":"keep","match_score":88,"reason":"..."}]}

SCORING (match_score 0–100):
90–100: Perfect — exact title, LLM/RAG/GenAI required, senior scope
75–89:  Strong — right domain, most skills match, appropriate seniority
55–74:  Decent — relevant title but partial overlap or unclear seniority
30–54:  Weak — related field but wrong stack or too junior
0–29:   Wrong role — reject

DECISION: "keep" if match_score >= 55 AND genuinely AI/ML engineering role.
"reject" everything else (pure analyst, BI, DevOps, etc.)."""


def _call_gemini(prompt: str) -> str:
    from agents._gemini import call_gemini
    return call_gemini(SYSTEM_PROMPT, prompt, max_tokens=4096)


def _call_claude(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text


def _parse(raw: str) -> List[dict]:
    text = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(text).get("scored_jobs", [])


def score_jobs(jobs: List[dict]) -> List[dict]:
    if not jobs:
        return []

    provider  = os.getenv("AI_PROVIDER", "gemini").lower()
    threshold = int(os.getenv("AI_SCORE_THRESHOLD", "55"))

    batch = [
        {
            "index":               i,
            "title":               j.get("title",""),
            "company":             j.get("company",""),
            "location":            j.get("location",""),
            "experience_level":    j.get("experience_level",""),
            "contract_type":       j.get("contract_type",""),
            "matched_keywords":    j.get("matched_keywords",""),
            "keyword_match_score": j.get("keyword_match_score",0),
            "description_preview": j.get("description","")[:600],
        }
        for i, j in enumerate(jobs)
    ]

    prompt = f"Score these {len(batch)} jobs:\n\n{json.dumps(batch)}"
    logger.info(f"[Scorer] Sending {len(batch)} jobs to {provider} …")

    raw = ""
    for attempt in range(3):
        try:
            raw = _call_gemini(prompt) if provider == "gemini" else _call_claude(prompt)
            break
        except Exception as e:
            wait = 10 * (attempt + 1)
            logger.warning(f"[Scorer] Attempt {attempt+1} failed: {e}. Retry in {wait}s …")
            time.sleep(wait)
    else:
        logger.error("[Scorer] All retries exhausted.")
        return []

    try:
        scored = _parse(raw)
    except Exception as e:
        logger.error(f"[Scorer] JSON parse error: {e}\nRaw: {raw[:400]}")
        return []

    kept = []
    for s in scored:
        if not isinstance(s, dict) or s.get("decision") != "keep":
            continue
        idx = s.get("index")
        if not isinstance(idx, int) or not (0 <= idx < len(jobs)):
            continue
        job = dict(jobs[idx])
        job["ai_match_score"]  = min(s.get("match_score", 0), 100)
        job["ai_match_reason"] = s.get("reason", "")
        kept.append(job)

    kept.sort(key=lambda x: x.get("ai_match_score", 0), reverse=True)
    result = [j for j in kept if j.get("ai_match_score", 0) >= threshold]
    logger.info(f"[Scorer] {len(result)} jobs kept (threshold={threshold}).")
    return result
