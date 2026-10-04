import os
import json
import re
from openai import OpenAI

FEATHERLESS_API_KEY = os.environ.get("FEATHERLESS_API_KEY", "")
FEATHERLESS_BASE = "https://api.featherless.ai/v1"
MODEL = "Qwen/Qwen2.5-7B-Instruct"

_client = None

def _get_client():
    global _client
    if _client is None:
        if not FEATHERLESS_API_KEY:
            return None
        _client = OpenAI(base_url=FEATHERLESS_BASE, api_key=FEATHERLESS_API_KEY)
    return _client

def prompt_json(system: str, user: str, max_tokens: int = 2000, temperature: float = 0.2) -> dict:
    """Send a prompt to Featherless, parse JSON from the response. Retries once on failure."""
    client = _get_client()
    if client is None:
        return {"error": "model_unavailable", "detail": "FEATHERLESS_API_KEY not set"}
    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            raw = resp.choices[0].message.content.strip()
            parsed = _extract_json(raw)
            return parsed
        except Exception:
            if attempt == 1:
                return {"error": "llm_failure", "detail": "Model returned malformed JSON after retry"}
    return {"error": "llm_failure", "detail": "Unknown error"}

def prompt_text(system: str, user: str, max_tokens: int = 1000, temperature: float = 0.7) -> str:
    """Send a prompt to Featherless, return raw text."""
    client = _get_client()
    if client is None:
        return "[llm unavailable: FEATHERLESS_API_KEY not set]"
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"[llm error: {e}]"

def _extract_json(raw: str) -> dict:
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw)
    if match:
        raw = match.group(1)
    return json.loads(raw.strip())