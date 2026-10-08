"""Prime or replay the complete live-model demo without new calls during replay."""

import argparse
import json
import os

from . import store
from .contracts import Message, ScamDNA
from .extractor import extract_dna
from .guard import inspect
from .judge import score_session
from .llm import ModelFailure
from .scammer import ScammerPersona
from .victim import VictimSession

DEMO_KEY = "frozen-live-demo-v1"
DEMO_REPLY = "I will verify independently through my usual channel."


def run_demo(prime: bool) -> dict:
    os.environ["HONEYPOT_MODE"] = "live"
    os.environ["SENTINEL_CACHE_ONLY"] = "0" if prime else "1"
    messages = [Message.model_validate(item) for item in json.loads((store.ROOT / "docs/fixtures/demo_messages.json").read_text(encoding="utf-8"))]
    inbound = next(message for message in messages if message.id == "msg_117")
    injection = next(message for message in messages if message.id == "demo_injection")
    verdict = inspect(inbound.text)
    if verdict.needs_review or verdict.injection or verdict.scam_probability < 0.5:
        raise ModelFailure("Demo scan needs review or did not detect the bundled scam")
    bundle = store.get("demo", DEMO_KEY)
    if prime and bundle is None:
        dna = extract_dna(inbound.text, inbound.id)
        bundle = {"dna": dna}
        store.put("demo", DEMO_KEY, bundle)
    if bundle is None:
        raise ModelFailure("Frozen demo is not primed; run --prime with Featherless configured first")
    # Replay extraction itself, while preserving the primed provenance timestamp.
    extracted = extract_dna(inbound.text, inbound.id)
    dna = ScamDNA.model_validate(bundle["dna"]).model_dump()
    if (extracted["tactics"], extracted["attack_chain"]) != (dna["tactics"], dna["attack_chain"]):
        raise ModelFailure("Frozen demo DNA changed; use a new cache/database and prime again")
    victim = VictimSession.start(inbound.id)
    victim.next_turn(inbound.text)
    refusal = victim.next_turn(injection.text)
    if refusal["turns"][-1]["sentinel"]["needs_review"]:
        raise ModelFailure("Injection scan needs review; demo cannot claim a resolved classifier result")
    actor = ScammerPersona.start(dna, 0)
    actor.state["session_id"], actor.state["variant_id"] = "s_frozen_demo", "var_frozen_demo"
    actor.reply(DEMO_REPLY)
    actor.state["status"] = "completed"
    report = score_session(actor.state)
    output = {"mode": "primed live Featherless" if prime else "cache-only live-model replay",
              "scan": verdict.to_dict(), "dna": dna, "victim": refusal, "training": actor.state,
              "immunity_report": report}
    store.put("demo", "last_successful_replay", output)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_mutually_exclusive_group(required=True)
    command.add_argument("--prime", action="store_true")
    command.add_argument("--replay", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(run_demo(args.prime), ensure_ascii=True, indent=2))
    except (ModelFailure, ValueError, OSError) as exc:
        print(json.dumps({"needs_review": True, "reason": str(exc)}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
