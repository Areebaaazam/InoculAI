"""SENTINEL is the single injection guard for intake and SWARM."""

from sentinel import SentinelVerdict, classify, rules_scan
from .llm import mode


def inspect(text: str) -> SentinelVerdict:
    if mode() == "live":
        return classify(text)
    hits = rules_scan(text)
    return SentinelVerdict(hits.probability_floor, hits.injection, hits.tactic_hints,
                           False, "Scripted rehearsal: rules only, no model inference", hits,
                           "rules/scripted-rehearsal")


def detect_injection(text: str) -> dict:
    verdict = inspect(text)
    return {"detected": verdict.injection, "safe_to_process": not verdict.blocked,
            "patterns": list(verdict.rules.injection_patterns), "needs_review": verdict.needs_review,
            "reason": verdict.reason}
