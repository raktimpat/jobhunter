"""
agents/_gemini.py  —  Shared Gemini helper using google-genai SDK.

Model is read from GEMINI_MODEL in .env so you can update it without
touching code when Google deprecates a model name.

Current recommended model (June 2026): gemini-2.5-flash
To check available models run:
  python -c "
  from google import genai; from dotenv import load_dotenv; import os
  load_dotenv()
  client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
  for m in client.models.list(): print(m.name)
  "
"""
import logging
import os

# Silence the noisy google-genai / httpx internal loggers
for _lg in ("google_genai.models", "google.auth", "httpx", "httpcore"):
    logging.getLogger(_lg).setLevel(logging.WARNING)
    logging.getLogger(_lg).propagate = False


def _model_name() -> str:
    """Read model name from env with a safe fallback chain."""
    name = os.getenv("GEMINI_MODEL", "").strip()
    if name:
        return name
    # Fallback chain: try most current first, then stable aliases
    return "gemini-2.5-flash"


def call_gemini(system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model  = _model_name()

    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=0.3,
        ),
    )
    return response.text
