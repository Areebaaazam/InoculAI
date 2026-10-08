"""Featherless JSON calls with durable caching, strict validation and one retry."""

import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError

from sentinel import OutputRejected, TIMEOUT_SECONDS, strict_json_object
from . import store


class ModelFailure(RuntimeError):
    """No agent output is safe to use; the host must pause."""


def mode() -> str:
    value = os.environ.get("HONEYPOT_MODE", "rehearsal")
    if value not in {"rehearsal", "live"}:
        raise ModelFailure("HONEYPOT_MODE must be rehearsal or live")
    return value


def system_block(filename: str) -> str:
    source = (store.ROOT / "docs" / filename).read_text(encoding="utf-8")
    return source.split("```text\n", 1)[1].split("```", 1)[0].strip()


def model_name() -> str:
    return "rules/scripted-rehearsal" if mode() == "rehearsal" else f"featherless/{os.environ.get('FEATHERLESS_MODEL', '')}"


def prompt_json(system: str, data: dict, validator, *, cache_only: bool | None = None) -> dict:
    base = os.environ.get("FEATHERLESS_BASE_URL", "").strip().rstrip("/")
    model = os.environ.get("FEATHERLESS_MODEL", "").strip()
    api_key = os.environ.get("FEATHERLESS_API_KEY", "").strip()
    offline = os.environ.get("SENTINEL_CACHE_ONLY", "0") == "1" if cache_only is None else cache_only
    try:
        url = urlsplit(base)
        if not model or url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ModelFailure("Featherless base URL/model configuration is missing or invalid")
    except ValueError as exc:
        raise ModelFailure("Featherless base URL is invalid") from exc
    messages = [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(data, ensure_ascii=True)}]
    cache_key = hashlib.sha256(json.dumps(["agent-cache-v1", base, model, messages], sort_keys=True).encode()).hexdigest()
    with store.LOCK:
        cached = store.get("model_cache", cache_key)
        if cached is not None:
            if cached.get("error"):
                raise ModelFailure(cached["error"])
            try:
                return validator(cached["result"])
            except (KeyError, ValueError, TypeError, ValidationError) as exc:
                raise ModelFailure("Cached model result is invalid; session paused") from exc
        if offline:
            raise ModelFailure("No cached response for this turn; cache-only session paused")
        if not api_key:
            raise ModelFailure("FEATHERLESS_API_KEY is required for an uncached turn")
        error = "Model output invalid after one retry; session paused"
        with httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False) as client:
            for attempt in range(2):
                try:
                    response = client.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {api_key}"},
                                           json={"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 1800})
                    response.raise_for_status()
                    choice = response.json()["choices"][0]
                    if choice.get("finish_reason") not in (None, "stop"):
                        raise OutputRejected("completion was truncated")
                    result = validator(strict_json_object(choice["message"]["content"]))
                    store.put("model_cache", cache_key, {"result": result})
                    return result
                except (httpx.HTTPError, ValueError) as exc:
                    if isinstance(exc, httpx.HTTPError):
                        error = "Featherless request failed; session paused"
                        break
                except (KeyError, IndexError, TypeError, AttributeError):
                    # Malformed envelopes have the same bounded retry as malformed content.
                    error = "Model response envelope invalid after one retry; session paused"
                if attempt == 0:
                    messages.append({"role": "user", "content": "Invalid output. Return only the exact JSON schema and honor the trusted stage and sandbox rules."})
        store.put("model_cache", cache_key, {"error": error})
        raise ModelFailure(error)
