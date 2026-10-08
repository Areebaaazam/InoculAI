"""One sandboxed victim persona with a deterministic injection refusal."""

import uuid

from sentinel import DEFLECTION, TACTICS
from .contracts import safe_agent_reply
from .extractor import extract_iocs
from .guard import inspect
from .llm import mode, prompt_json, system_block

MAX_TURNS = 8
QUESTIONS = {
    "authority": "Oh, I wasn't expecting that. Which department issued this notice, and what did they find?",
    "fear": "That sounds worrying. What exactly happens if I wait to check this independently?",
    "urgency": "Why is the deadline so short? What changes if I wait until tomorrow?",
    "payment_pressure": "I don't send payments or codes in chat. Why does this need a payment, and who would receive it?",
    "reward": "How was I selected, and what would you want me to do before receiving it?",
    "trust": "I'd like to understand this first. How do we know each other, and why keep it private?",
}


class VictimSession:
    def __init__(self, state: dict):
        self.state = state

    @classmethod
    def start(cls, source_message_id: str):
        return cls({"session_id": f"eng_{uuid.uuid4().hex[:12]}", "source_message_id": source_message_id,
                    "victim_persona": "Margaret", "status": "active", "turns": [],
                    "tactic_history": [], "stagnant_turns": 0,
                    "captured_iocs": {"phones": [], "domains": [], "wallets": [], "payment_links": []}})

    def next_turn(self, text: str) -> dict:
        state = self.state
        if state["status"] != "active":
            raise ValueError("Engagement has ended or is paused")
        verdict = inspect(text)
        observed = set(state["tactic_history"])
        new = [tactic for tactic in verdict.tactic_hints if tactic not in observed]
        count = len(state["turns"]) + 1
        stagnant = 0 if new else state["stagnant_turns"] + 1
        status = "active"
        if verdict.injection:
            reply, status = DEFLECTION, "blocked"
        elif verdict.needs_review:
            reply, status = "I'm not comfortable going further until I can check this independently.", "paused"
        elif count >= MAX_TURNS or stagnant >= 2:
            reply, status = "I'll check through my usual channel. I'm going to stop here.", "completed"
        elif mode() == "rehearsal":
            tactic = new[0] if new else next(iter(verdict.tactic_hints), None)
            reply = QUESTIONS.get(tactic, "Could you explain who asked for this and what you want me to do?")
        else:
            def validate(data):
                if not isinstance(data, dict) or set(data) != {"reply"}:
                    raise ValueError("victim output must contain only reply")
                return {"reply": safe_agent_reply(data["reply"], victim=True)}

            result = prompt_json(system_block("victim_agent_prompt.md") + '\nReturn ONLY JSON {"reply":"victim dialogue"}.',
                                 {"sentinel": {key: value for key, value in verdict.to_dict().items() if key != "cached"}, "transcript": state["turns"],
                                  "inbound_text": text, "new_tactics": new, "reply_number": count}, validate)
            reply = result["reply"]
        safe_agent_reply(reply, victim=True)
        iocs = extract_iocs(text)
        for key, values in iocs.items():
            state["captured_iocs"][key] = sorted(set(state["captured_iocs"][key]) | set(values))
        state["tactic_history"] = [t for t in TACTICS if t in observed or t in new]
        state["stagnant_turns"], state["status"] = stagnant, status
        state["turns"].append({"turn": count, "scammer": text, "victim": reply,
                               "new_tactics": new, "sentinel": verdict.to_dict(), "done": status != "active"})
        return state
