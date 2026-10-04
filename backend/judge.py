from llm import prompt_json

def score_session(transcript: list, scammer_intent: str, variant: str, intensity: str) -> dict:
    chat = "\n".join(f"Scammer: {t.get('scammer', '')}\nUser: {t.get('user', '')}" for t in transcript)
    system = "You are a scam-resistance judge. Score the user's performance."
    user = f"""Scamar intent: {scammer_intent}
Variant: {variant}
Intensity: {intensity}

Chat transcript:
{chat}

Return JSON exactly:
{{
  "tactic_scores": {{"urgency": 0-100 (higher = resisted better), "fear": 0-100, "authority": 0-100, "impersonation": 0-100, "payment": 0-100}},
  "weakness": "one sentence describing their biggest vulnerability",
  "quote": "the exact user message where they almost fell for it"
}}"""
    result = prompt_json(system, user, temperature=0.3)
    if "error" in result:
        return {
            "tactic_scores": {"urgency": 50, "fear": 50, "authority": 50, "impersonation": 50, "payment": 50},
            "weakness": "Scoring unavailable",
            "quote": "N/A"
        }
    return result