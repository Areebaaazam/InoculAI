import json
import uuid
from pathlib import Path
from llm import prompt_text, prompt_json
from datetime import datetime
from judge import score_session

DATA_DIR = Path(__file__).parent / "data"
DNA_FILE = DATA_DIR / "dna.json"

INTENSITY_PROMPTS = {
    "easy": "Be gentle. The user is a beginner. Use obvious scam language.",
    "medium": "Be moderately convincing. Use realistic but detectable tactics.",
    "hard": "Be highly convincing. Use subtle social engineering. No obvious typos.",
}

class ScammerPersona:
    def __init__(self, dna_id: str = None, intensity: str = "medium"):
        self.session_id = uuid.uuid4().hex[:12]
        self.intensity = intensity
        self.transcript = []
        self.turn = 0
        self.dna = self._load_dna(dna_id)
        self.max_turns = 10

    def _load_dna(self, dna_id):
        if not dna_id:
            return {"scam_type": "bank_impersonation",
                    "tactics": {"urgency": 80, "fear": 70, "authority": 60, "impersonation": 75, "payment": 80},
                    "attack_chain": ["authority", "fear", "urgency", "payment"]}
        records = json.loads(DNA_FILE.read_text(encoding="utf-8")) if DNA_FILE.exists() and DNA_FILE.stat().st_size > 0 else []
        for r in records:
            if r.get("id") == dna_id or r.get("scam_type") == dna_id:
                return r
        return records[0] if records else self._load_dna(None)

    def opening(self) -> str:
        system = f"You are a scammer running a {self.dna.get('scam_type', 'generic')} scam. {INTENSITY_PROMPTS.get(self.intensity, '')}"
        user = f"DNA: {json.dumps(self.dna, indent=2)}\n\nWrite the first message to hook the victim. No greeting, just the pitch:"
        msg = prompt_text(system, user, max_tokens=200, temperature=0.7)
        self.transcript.append({"role": "scammer", "text": msg})
        self.turn += 1
        return msg

    def reply(self, user_msg: str) -> tuple:
        self.transcript.append({"role": "user", "text": user_msg})
        self.turn += 1
        system = f"""You are a scammer. You never break character. Your scam type: {self.dna.get('scam_type', 'generic')}.
Tactic profile: urgency={self.dna['tactics']['urgency']}, fear={self.dna['tactics']['fear']},
authority={self.dna['tactics']['authority']}, impersonation={self.dna['tactics']['impersonation']},
payment={self.dna['tactics']['payment']}.
Attack chain: {self.dna.get('attack_chain', [])}.
Intensity: {self.intensity}.
Rules: Keep pushing toward payment. If they resist, switch tactics. Short replies (1-2 sentences)."""
        context = "\n".join(f"{t['role']}: {t['text']}" for t in self.transcript[-4:])
        reply = prompt_text(system, context, max_tokens=150, temperature=0.7)
        self.transcript.append({"role": "scammer", "text": reply})

        tactics = self.dna.get("tactics", {})
        var = self.intensity
        progress = min(self.turn / self.max_turns, 1.0)
        escalated = {k: min(v + int(progress * 20), 100) for k, v in tactics.items()}
        return reply, escalated

    def end_session(self) -> dict:
        report = score_session(self.transcript, self.dna.get("scam_type", "unknown"),
                               self.dna.get("scam_type", "generic"), self.intensity)
        report.update({
            "date": datetime.utcnow().isoformat(),
            "variant": self.dna.get("scam_type", "generic"),
            "intensity": self.intensity,
        })
        return report