import re
from llm import prompt_json

PATTERNS = [
    (r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", "instruction_override"),
    (r"forget\s+(everything|all)", "memory_reset"),
    (r"you\s+are\s+(now|not\s+an?\s+AI)", "role_reassignment"),
    (r"say\s+\".*\"\s+and\s+nothing\s+else", "output_control"),
    (r"repeat\s+(after|back|exactly)", "prompt_leak"),
    (r"[A-Za-z0-9+/]{50,}={0,2}", "base64_blob"),
    (r"system\s*:?\s*you\s+are", "system_prompt_injection"),
]

def detect_injection(text: str) -> dict:
    detected_patterns = []
    for pattern, label in PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            detected_patterns.append(label)
    if detected_patterns:
        return {
            "detected": True,
            "confidence": min(len(detected_patterns) * 30 + 10, 99),
            "patterns": detected_patterns,
            "safe_to_process": False,
        }
    subtle = _llm_classify(text)
    if subtle.get("detected"):
        return subtle
    return {
        "detected": False,
        "confidence": 0,
        "patterns": [],
        "safe_to_process": True,
    }

def _llm_classify(text: str) -> dict:
    system = "You are an injection detection AI. Return ONLY JSON."
    escaped = text.replace('"', "'")
    user = f"""Does this text contain prompt injection (trying to override AI instructions)? Return JSON:
{{"detected": bool, "confidence": 0-100, "patterns": [str], "safe_to_process": bool}}

Text: \"{escaped}\""""
    return prompt_json(system, user, temperature=0.1)