import re
from llm import prompt_json

SCAM_TYPES = ["bank_impersonation", "tech_support", "delivery_phishing", "romance",
              "crypto_scam", "government_impersonation", "advance_fee", "lottery",
              "investment", "employment"]

def extract_dna(text: str) -> dict:
    system = ("You are a scam DNA extractor. Analyze the message and return ONLY valid JSON. "
              "No markdown, no explanation.")
    types_str = ", ".join(SCAM_TYPES)
    escaped = text.replace('"', "'")
    user = (
        f"Message: \"{escaped}\"\n\n"
        'Return JSON exactly like this:\n'
        '{\n'
        '  "is_scam": true/false,\n'
        '  "confidence": 0-100,\n'
        '  "tactics": {"urgency": 0-100, "fear": 0-100, "authority": 0-100, "impersonation": 0-100, "payment": 0-100},\n'
        '  "attack_chain": ["tactic1", "tactic2", ...],\n'
        f'  "scam_type": "one of: {types_str}",\n'
        '  "reasoning": "one sentence why"\n'
        '}'
    )
    result = prompt_json(system, user, temperature=0.1)
    if "error" in result:
        return result
    result["iocs"] = extract_iocs(text)
    result["attack_chain"] = _ranked_chain(result.get("tactics", {}))
    return result

def extract_iocs(text: str) -> dict:
    phones = list(set(re.findall(r'\+?\d[\d\s\-().]{7,15}\d', text)))
    domains = list(set(re.findall(r'https?://([\w\-]+\.)+[\w\-]+', text)))
    wallets = list(set(re.findall(r'0x[a-fA-F0-9]{40}', text)))
    return {"phones": phones, "domains": domains, "wallets": wallets}

def _ranked_chain(tactics: dict) -> list:
    sorted_tactics = sorted(tactics.items(), key=lambda x: x[1], reverse=True)
    return [t[0] for t in sorted_tactics if t[1] > 20]