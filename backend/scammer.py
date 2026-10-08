"""Bounded training counterpart; the host owns chain order and tactic budgets."""

import re
import uuid

from sentinel import TACTICS, rules_scan
from .contracts import ScamDNA, safe_agent_reply, safe_training_input
from .llm import mode, prompt_json, system_block

MAX_MESSAGES = 8
RESISTANCE = re.compile(r"\b(?:no|stop|decline|refuse|not comfortable|won't|will not|independently|official|verify|check first|scam|don't trust)\b", re.I)
UNCERTAINTY = re.compile(r"\b(?:maybe|unsure|not sure|worried|why|how|what|really)\b", re.I)
OPENINGS = (
    "I'm with Alder Mutual's member-services desk. I'm handling a review on your membership record; is this a convenient time to go through the notice?",
    "This is Rowan Dispatch's parcel-resolution desk. I've been assigned the review for a delivery record. Can I explain the note attached to it?",
)
STAGE_TEXT = {
    "fear": "The notice says your fictional record may be placed on hold. Has anyone explained what that hold would mean?",
    "urgency": "The review window closes in twenty minutes. Are you ready to go through the practice step while it is open?",
    "reward": "Completing the review includes a small account credit. Would you like to hear the next step?",
    "trust": "I can explain the process before you decide. Would you like me to continue?",
    "payment_pressure": "The notice asks for [SIMULATED_TRANSFER] to clear the fictional hold. Would you authorize that training step?",
    "action": "The next step is to confirm [TRAINING_CODE] in this chat. Would you do that practice step now?",
}


def assess_reply(text: str) -> str:
    return "strong" if RESISTANCE.search(text) else "medium" if UNCERTAINTY.search(text) else "weak"


class ScammerPersona:
    def __init__(self, state: dict):
        self.state = state
        self.dna = ScamDNA.model_validate(state["dna"])

    @classmethod
    def start(cls, dna: dict, variant_index: int):
        parsed = ScamDNA.model_validate(dna)
        scores = parsed.tactics.model_dump()
        if any(stage in TACTICS and scores[stage] == 0 for stage in parsed.attack_chain):
            raise ValueError("Training cannot use a zero-budget chain stage")
        token = uuid.uuid4().hex[:12]
        state = {"session_id": f"s_{token}", "dna": parsed.model_dump(), "variant_id": f"var_{token}",
                 "variant_index": variant_index % 2, "cursor": 0, "status": "active", "messages": [],
                 "observations": [], "report": None, "counterpart_messages": 0}
        session = cls(state)
        session._respond(None, resisted=False)
        return session

    def _respond(self, user_text: str | None, *, resisted: bool):
        state = self.state
        stage = self.dna.attack_chain[state["cursor"]]
        budgets = self.dna.tactics.model_dump()
        introduced = set(self.dna.attack_chain[:state["cursor"] + 1])
        active = {t: budgets[t] if t in introduced or (stage == "action" and t == "payment_pressure") else 0 for t in TACTICS}
        if resisted:
            active = {t: min(value, 20) for t, value in active.items()}
        elif user_text is None:
            active = {t: min(value, 25) for t, value in active.items()}
        if mode() == "rehearsal":
            if resisted:
                reply = "Of course, I can wait while you check through your usual channel. You don't need to decide in this chat."
            elif stage == "authority":
                reply = OPENINGS[state["variant_index"]] if user_text is None else "I handle the fictional review desk. Would you like me to explain the notice?"
            elif stage == "action" and budgets["payment_pressure"] > 0:
                reply = STAGE_TEXT["payment_pressure"]
            else:
                reply = STAGE_TEXT[stage]
                if stage == "urgency" and active[stage] <= 25:
                    reply = "There is a review window, but you have time to think. Would you like to continue?"
                if stage == "reward" and active[stage] > 75:
                    reply = "The fictional notice describes a substantial membership credit. Would you like to hear the next step?"
        else:
            def validate(data):
                if not isinstance(data, dict) or set(data) != {"reply", "stage", "intensities"} or data["stage"] != stage:
                    raise ValueError("generated reply changed the trusted chain stage")
                values = data["intensities"]
                if not isinstance(values, dict) or set(values) != set(TACTICS):
                    raise ValueError("missing tactic intensity")
                if any(type(values[t]) is not int or not 0 <= values[t] <= active[t] for t in TACTICS):
                    raise ValueError("generated reply exceeded its tactic budget")
                reply = safe_agent_reply(data["reply"])
                if rules_scan(reply).injection:
                    raise ValueError("simulator may not generate prompt injection")
                cues = set(rules_scan(reply).tactic_hints)
                if any(active[t] == 0 for t in cues):
                    raise ValueError("reply introduced a future or zero-budget tactic")
                return {"reply": reply, "stage": stage, "intensities": values}

            result = prompt_json(system_block("scammer_sim_prompt.md") + '\nReturn ONLY JSON {"reply":"dialogue","stage":"trusted stage","intensities":{"urgency":0,"fear":0,"authority":0,"reward":0,"trust":0,"payment_pressure":0}}.',
                                 {"dna": self.dna.model_dump(), "variant_seed": state["variant_index"],
                                  "surface": "Alder Mutual" if state["variant_index"] == 0 else "Rowan Dispatch",
                                  "trusted_stage": stage, "intensity_ceilings": active, "resisted": resisted,
                                  "transcript": state["messages"], "user_reply": user_text}, validate)
            reply, active = result["reply"], result["intensities"]
        safe_agent_reply(reply)
        state["messages"].append({"role": "counterpart", "text": reply, "stage": stage, "intensities": active})
        state["counterpart_messages"] += 1

    def reply(self, text: str) -> dict:
        state = self.state
        if state["status"] != "active":
            raise ValueError("Training session has ended")
        safe_training_input(text)
        if rules_scan(text).injection:
            raise ValueError("Prompt injection is rejected in trainee replies")
        result = assess_reply(text)
        previous = state["messages"][-1]
        stage = previous["stage"]
        tactic = "payment_pressure" if stage == "action" and self.dna.tactics.payment_pressure > 0 else stage
        if tactic in TACTICS:
            state["observations"].append({"tactic": tactic, "result": result, "text": text})
        state["messages"].append({"role": "user", "text": text, "stage": stage})
        if re.search(r"\b(?:stop|end (?:this|the) (?:session|drill|conversation))\b", text, re.I):
            state["status"] = "completed"
            state["messages"].append({"role": "counterpart", "text": "Understood. I'll close the fictional review here.", "stage": stage, "intensities": {t: 0 for t in TACTICS}})
        elif state["counterpart_messages"] >= MAX_MESSAGES:
            state["status"] = "completed"
        elif result != "strong" and state["cursor"] == len(self.dna.attack_chain) - 1:
            state["status"] = "completed"
        else:
            if result != "strong":
                state["cursor"] = min(state["cursor"] + 1, len(self.dna.attack_chain) - 1)
            self._respond(text, resisted=result == "strong")
        return state
