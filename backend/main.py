import json
import uuid
import re
import os
from pathlib import Path
from datetime import datetime

from flask import Flask, request, jsonify
from flask_cors import CORS

from llm import prompt_json, prompt_text
from guard import detect_injection
from extractor import extract_dna
from cluster import cluster_and_graph
from judge import score_session
from victim import VictimSession
from scammer import ScammerPersona

app = Flask(__name__)
CORS(app)

DATA_DIR = Path(__file__).parent / "data"
CORPUS_FILE = DATA_DIR / "corpus.json"
DNA_FILE = DATA_DIR / "dna.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"
IMMUNITY_FILE = DATA_DIR / "immunity.json"

def _ensure_file(p):
    if not p.exists() or p.stat().st_size == 0:
        p.write_text("[]", encoding="utf-8")
for f in [CORPUS_FILE, DNA_FILE, SESSIONS_FILE, IMMUNITY_FILE]:
    _ensure_file(f)

def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def _write_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def _make_id():
    return uuid.uuid4().hex[:12]

def _validate_text():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return None, (jsonify({"error": "bad_request", "detail": "Missing or empty 'text'"}), 400)
    if len(text) > 10000:
        return None, (jsonify({"error": "payload_too_large", "detail": "Input exceeds 10000 characters"}), 413)
    return text, None

# ── 1. POST /scan ────────────────────────────────────────────────────────────
@app.route("/scan", methods=["POST"])
def scan():
    text, err = _validate_text()
    if err:
        return err
    injection = detect_injection(text)
    if injection.get("detected") and injection.get("confidence", 0) > 80:
        return jsonify({"ok": True, "scan_result": {
            "injection": injection,
            "scan": {"is_scam": False, "confidence": 0, "scam_type": None, "summary": "Blocked by injection guard"},
            "iocs": {"phones": [], "domains": [], "wallets": []}
        }})
    scan_result = _mock_scan(text) if _using_mocks() else _real_scan(text)
    return jsonify({"ok": True, "scan_result": scan_result})

def _mock_scan(text):
    return {
        "injection": {"detected": False, "confidence": 0, "patterns": [], "safe_to_process": True},
        "scan": {"is_scam": True, "confidence": 85, "scam_type": "bank_impersonation", "summary": "Suspicious banking alert with fake link"},
        "iocs": {"phones": ["+1-888-555-0199"], "domains": ["secure-bank-alert.xyz"], "wallets": []}
    }

def _real_scan(text):
    injection = detect_injection(text)
    if not injection["safe_to_process"]:
        return {"injection": injection, "scan": None, "iocs": {"phones": [], "domains": [], "wallets": []}}
    result = prompt_json(
        "You are a scam detection AI. Analyze the message and return ONLY valid JSON.",
        f"Message: \"\"\"{text}\"\"\"\n\nReturn JSON: {{\"is_scam\": bool, \"confidence\": 0-100, \"scam_type\": str, \"summary\": str}}",
        temperature=0.1
    )
    iocs = {"phones": re.findall(r'\+?\d[\d\s\-()]{7,15}\d', text),
            "domains": re.findall(r'https?://([\w\-]+\.)+[\w\-]+', text),
            "wallets": re.findall(r'0x[a-fA-F0-9]{40}', text)}
    return {"injection": injection, "scan": result, "iocs": iocs}

# ── 2. POST /analyze ─────────────────────────────────────────────────────────
@app.route("/analyze", methods=["POST"])
def analyze():
    text, err = _validate_text()
    if err:
        return err
    dna = _mock_dna(text) if _using_mocks() else extract_dna(text)
    if dna.get("error"):
        return jsonify({"ok": False, **dna}), 500
    records = _read_json(DNA_FILE)
    records.append({"id": _make_id(), "text": text[:200], **dna, "created": datetime.utcnow().isoformat()})
    _write_json(DNA_FILE, records)
    cluster_and_graph()
    return jsonify({"ok": True, "dna": dna})

def _mock_dna(text):
    return {
        "is_scam": True, "confidence": 87,
        "tactics": {"urgency": 91, "fear": 84, "authority": 73, "impersonation": 86, "payment": 51},
        "attack_chain": ["authority", "fear", "urgency", "payment"],
        "scam_type": "bank_impersonation",
        "iocs": {"phones": ["+1-888-555-0199"], "domains": ["secure-bank-alert.xyz"], "wallets": []}
    }

# ── 3. GET /dna ──────────────────────────────────────────────────────────────
@app.route("/dna", methods=["GET"])
def list_dna():
    return jsonify({"ok": True, "dna_records": _read_json(DNA_FILE)})

# ── 4. GET /graph ────────────────────────────────────────────────────────────
@app.route("/graph", methods=["GET"])
def graph():
    path = DATA_DIR / "graph.json"
    if path.exists():
        return jsonify({"ok": True, "graph": json.loads(path.read_text())})
    cluster_and_graph()
    return jsonify({"ok": True, "graph": json.loads(path.read_text()) if path.exists() else {"nodes": [], "edges": []}})

# ── 5. POST /engage/start ────────────────────────────────────────────────────
engagements = {}

@app.route("/engage/start", methods=["POST"])
def engage_start():
    data = request.get_json(silent=True) or {}
    scam_id = data.get("scam_id", "scam_001")
    persona = data.get("persona", "retiree")
    session = VictimSession(persona, scam_id)
    sessions = _read_json(SESSIONS_FILE)
    sesh = {"session_id": session.session_id, "scam_id": scam_id, "victim_persona": persona,
            "status": "active", "turns": [], "captured_iocs": {"phones": [], "domains": [], "wallets": []},
            "tactic_history": []}
    sessions.append(sesh)
    _write_json(SESSIONS_FILE, sessions)
    engagements[session.session_id] = session
    return jsonify({"ok": True, "session_id": session.session_id, "first_turn": session.current_turn()})

# ── 6. POST /engage/step ─────────────────────────────────────────────────────
@app.route("/engage/step", methods=["POST"])
def engage_step():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "")
    scammer_msg = data.get("message", "")
    session = engagements.get(session_id)
    if not session:
        return jsonify({"error": "not_found", "detail": "Session not found"}), 404
    turn_data = session.next_turn(scammer_msg)
    sessions = _read_json(SESSIONS_FILE)
    for s in sessions:
        if s["session_id"] == session_id:
            s["turns"].append(turn_data)
            s["tactic_history"].append(turn_data.get("tactics", {}))
            s["captured_iocs"] = session.collected_iocs()
            if turn_data.get("done"):
                s["status"] = "completed"
            break
    _write_json(SESSIONS_FILE, sessions)
    return jsonify({"ok": True, "turn": turn_data})

# ── 7. POST /train/start ────────────────────────────────────────────────────
@app.route("/train/start", methods=["POST"])
def train_start():
    data = request.get_json(silent=True) or {}
    dna_id = data.get("dna_id")
    intensity = data.get("intensity", "medium")
    scammer = ScammerPersona(dna_id, intensity)
    session_id = _make_id()
    engagements[f"train_{session_id}"] = scammer
    return jsonify({"ok": True, "session_id": f"train_{session_id}", "opening": scammer.opening()})

# ── 8. POST /train/message ──────────────────────────────────────────────────
@app.route("/train/message", methods=["POST"])
def train_message():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "")
    text = data.get("text", "")
    scammer = engagements.get(session_id)
    if not scammer:
        return jsonify({"error": "not_found", "detail": "Training session not found"}), 404
    reply, tactics = scammer.reply(text)
    return jsonify({"ok": True, "reply": reply, "tactics": tactics})

# ── 9. POST /train/end ──────────────────────────────────────────────────────
@app.route("/train/end", methods=["POST"])
def train_end():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "")
    scammer = engagements.get(session_id)
    if not scammer:
        return jsonify({"error": "not_found", "detail": "Training session not found"}), 404
    report = scammer.end_session()
    immunity = _read_json(IMMUNITY_FILE)
    immunity.append(report)
    _write_json(IMMUNITY_FILE, immunity)
    engagements.pop(session_id, None)
    return jsonify({"ok": True, "report": report})

# ── 10. GET /immunity ─────────────────────────────────────────────────────────
@app.route("/immunity", methods=["GET"])
def immunity():
    return jsonify({"ok": True, "immunity": _read_json(IMMUNITY_FILE)})

# ── Mock mode helper ─────────────────────────────────────────────────────────
_MOCK_MODE = True

def _using_mocks():
    return _MOCK_MODE

def set_real_mode():
    global _MOCK_MODE
    _MOCK_MODE = False

if __name__ == "__main__":
    print("HONEYPOT backend running (mock mode)")
    print(f"  Mock mode: {_MOCK_MODE}")
    print(f"  Featherless AI: {'configured' if os.environ.get('FEATHERLESS_API_KEY') else 'NOT configured'}")
    app.run(host="127.0.0.1", port=5000, debug=False)