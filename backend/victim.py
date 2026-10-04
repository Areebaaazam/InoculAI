import uuid
import re
from llm import prompt_text, prompt_json
from extractor import extract_iocs

PERSONAS = {
    "retiree": {
        "name": "Margaret",
        "age": 72,
        "backstory": "Retired teacher living alone. Uses email for family photos and bank alerts. Trusts authority figures.",
        "patience": 8,
        "suspicion_threshold": 65,
    },
    "international_student": {
        "name": "Priya",
        "age": 22,
        "backstory": "First-year CS master's student from India. New to the country, unsure about local processes. Anxious about visa/legal issues.",
        "patience": 7,
        "suspicion_threshold": 55,
    },
    "small_business_owner": {
        "name": "Carlos",
        "age": 45,
        "backstory": "Runs a local bakery. Busy, stressed, answers calls while multitasking. Has fallen for a phishing email before.",
        "patience": 5,
        "suspicion_threshold": 45,
    },
    "tech_savvy_teen": {
        "name": "Jordan",
        "age": 17,
        "backstory": "Grew up online, knows what phishing looks like but gets hooked by free stuff and gaming scams.",
        "patience": 9,
        "suspicion_threshold": 70,
    },
}

class VictimSession:
    def __init__(self, persona_name: str, scam_id: str, max_turns: int = 12):
        self.session_id = uuid.uuid4().hex[:12]
        self.persona = PERSONAS.get(persona_name, PERSONAS["retiree"])
        self.scam_id = scam_id
        self.max_turns = max_turns
        self.turn = 0
        self.transcript = []
        self.tactic_scores = {"urgency": 0, "fear": 0, "authority": 0, "impersonation": 0, "payment": 0}
        self.collected_iocs_data = {"phones": [], "domains": [], "wallets": []}
        self.stage = "curious"
        self.done = False

    def current_turn(self) -> dict:
        return {"turn": 0, "role": "system",
                "message": f"You are {self.persona['name']}. Ready to engage. Waiting for scammer message."}

    def collected_iocs(self) -> dict:
        return self.collected_iocs_data

    def next_turn(self, scammer_msg: str) -> dict:
        self.turn += 1
        self.transcript.append({"role": "scammer", "text": scammer_msg})

        new_iocs = extract_iocs(scammer_msg)
        for k in self.collected_iocs_data:
            self.collected_iocs_data[k].extend(new_iocs.get(k, []))
            self.collected_iocs_data[k] = list(set(self.collected_iocs_data[k]))

        self._update_tactics(scammer_msg)
        self._update_stage()

        if self.turn >= self.max_turns:
            self.done = True
            reply = f"[{self.persona['name']} ends the conversation] I'm going to call the official number instead. Goodbye."
        elif self.stage == "stalling" and self.turn > 3:
            reply = self._llm_reply(scammer_msg)
        else:
            reply = self._llm_reply(scammer_msg)

        self.transcript.append({"role": "victim", "text": reply})

        return {
            "turn": self.turn,
            "scammer": scammer_msg,
            "victim": reply,
            "tactics": dict(self.tactic_scores),
            "stage": self.stage,
            "done": self.done,
            "iocs": new_iocs,
        }

    def _llm_reply(self, scammer_msg: str) -> str:
        context = "\n".join(f"{t['role']}: {t['text']}" for t in self.transcript[-6:])
        system = f"""You are {self.persona['name']}, age {self.persona['age']}.
Backstory: {self.persona['backstory']}
Stage: {self.stage}
Rules: Never pay money. Never give real personal info. Use fake details if pressured.
Your goal: Keep the scammer talking, act interested, stall. Be natural."""
        user = f"Scammer says: \"{scammer_msg}\"\n\nRespond in character as {self.persona['name']}, keeping them on the line:"
        return prompt_text(system, user, max_tokens=150, temperature=0.8)

    def _update_tactics(self, msg: str):
        lower = msg.lower()
        urgency_words = ["urgent", "immediately", "now", "today", "24 hours", "limited", "expires", "act now"]
        fear_words = ["suspended", "blocked", "locked", "legal", "police", "arrest", "fine", "penalty", "fraud"]
        authority_words = ["official", "government", "bank", "manager", "director", "department", "authorized"]
        impersonation_words = ["your bank", "your provider", "your account", "we detected", "we noticed"]
        payment_words = ["pay", "send", "transfer", "wire", "bitcoin", "gift card", "credit card", "fee", "deposit"]

        scores = {
            "urgency": sum(lower.count(w) for w in urgency_words) * 10,
            "fear": sum(lower.count(w) for w in fear_words) * 10,
            "authority": sum(lower.count(w) for w in authority_words) * 10,
            "impersonation": sum(lower.count(w) for w in impersonation_words) * 10,
            "payment": sum(lower.count(w) for w in payment_words) * 10,
        }
        for k in self.tactic_scores:
            self.tactic_scores[k] = min(self.tactic_scores.get(k, 0) + scores.get(k, 0), 100)

    def _update_stage(self):
        avg = sum(self.tactic_scores.values()) / max(len(self.tactic_scores), 1)
        if avg > 70:
            self.stage = "stalling"
        elif avg > 40:
            self.stage = "hesitant"
        elif self.turn > 2:
            self.stage = "engaged"
        else:
            self.stage = "curious"