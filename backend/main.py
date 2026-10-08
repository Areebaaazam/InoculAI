"""HONEYPOT: intake -> SENTINEL -> SWARM/DNA -> TRAIN ME -> immunity report."""

import json
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import StrictBool

from sentinel import scan as sentinel_scan
from . import store
from .cluster import assign_campaign, cluster_and_graph
from .contracts import (Contract, EngagementStart, ImmunityReport, Message, ScamDNA,
                        SessionInput, TextInput, TrainingInput, TrainingStart)
from .extractor import extract_dna, extract_iocs
from .guard import inspect
from .judge import score_session
from .llm import ModelFailure, mode
from .scammer import ScammerPersona
from .victim import VictimSession


@asynccontextmanager
async def lifespan(application):
    mode()
    with store.LOCK:
        messages = json.loads((store.ROOT / "docs/fixtures/demo_messages.json").read_text(encoding="utf-8"))
        corpus = json.loads((store.ROOT / "backend/data/corpus.json").read_text(encoding="utf-8"))
        messages.extend({"id": f"corpus_{index:03d}", "channel": "chat", "text": item["text"],
                         "sender": "fictional_bundled_corpus", "timestamp": messages[0]["timestamp"]}
                        for index, item in enumerate(corpus, 1))
        for raw in messages:
            message = Message.model_validate(raw).model_dump()
            if store.get("messages", message["id"]) is None:
                store.put("messages", message["id"], message)
        dna = ScamDNA.model_validate(json.loads((store.ROOT / "docs/fixtures/scam_dna.json").read_text(encoding="utf-8"))).model_dump()
        dna["extraction_model"] = "curated/reference"
        dna["iocs"] = extract_iocs(next(item["text"] for item in messages if item["id"] == dna["source_message_id"]))
        if store.get("dna", dna["id"]) is None:
            store.put("dna", dna["id"], dna)
    yield


app = FastAPI(title="HONEYPOT", version="1.0.0", lifespan=lifespan)
app.mount("/assets", StaticFiles(directory=store.ROOT / "frontend"), name="assets")
app.add_api_route("/sentinel/scan", sentinel_scan, methods=["POST"])


@app.exception_handler(ModelFailure)
async def model_failure(request: Request, exc: ModelFailure):
    return JSONResponse(status_code=503, content={"error": "needs_review", "detail": str(exc), "needs_review": True})


@app.exception_handler(ValueError)
async def rejected_input(request: Request, exc: ValueError):
    return JSONResponse(status_code=422, content={"error": "input_rejected", "detail": str(exc)})


@app.exception_handler(sqlite3.Error)
async def storage_failure(request: Request, exc: sqlite3.Error):
    return JSONResponse(status_code=503, content={"error": "storage_unavailable", "detail": "Local storage is unavailable; request blocked", "needs_review": True})


@app.exception_handler(KeyError)
@app.exception_handler(TypeError)
@app.exception_handler(IndexError)
@app.exception_handler(OSError)
async def unavailable_state(request: Request, exc: Exception):
    return JSONResponse(status_code=503, content={"error": "invalid_state", "detail": "Application state is unreadable or invalid; request blocked", "needs_review": True})


def require_synthetic(confirmed: bool):
    if not confirmed:
        raise ValueError("Only fictional or synthetic inbound messages are allowed")


def required(bucket: str, record_id: str) -> dict:
    result = store.get(bucket, record_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"{bucket} record not found")
    return result


def resolve_message(message: Message) -> dict:
    verdict = inspect(message.text)
    store.put("messages", message.id, message.model_dump())
    store.put("scans", message.id, verdict.to_dict())
    dna = None
    if not verdict.blocked and verdict.scam_probability >= 0.5:
        dna = assign_campaign(extract_dna(message.text, message.id), store.all_records("dna"))
        store.put("dna", dna["id"], dna)
    return {"ok": True, "message": message.model_dump(), "verdict": verdict.to_dict(), "dna": dna}


@app.get("/")
def home():
    return FileResponse(store.ROOT / "frontend/index.html")


@app.get("/styles.css", include_in_schema=False)
def styles():
    return FileResponse(store.ROOT / "frontend/styles.css", media_type="text/css")


@app.get("/app.js", include_in_schema=False)
def javascript():
    return FileResponse(store.ROOT / "frontend/app.js", media_type="application/javascript")


@app.get("/health")
def health():
    return {"ok": True, "mode": mode(), "persona": "Margaret", "cache_only": os.environ.get("SENTINEL_CACHE_ONLY") == "1",
            "model_configured": all(os.environ.get(key) for key in ("FEATHERLESS_BASE_URL", "FEATHERLESS_MODEL", "FEATHERLESS_API_KEY"))}


@app.get("/corpus")
def corpus():
    return {"ok": True, "messages": [Message.model_validate(item).model_dump() for item in store.all_records("messages")]}


class IntakeInput(Contract):
    message: Message
    synthetic: StrictBool


@app.post("/intake")
def intake(request: IntakeInput):
    require_synthetic(request.synthetic)
    with store.LOCK:
        prior = store.get("messages", request.message.id)
        if prior is not None and prior != request.message.model_dump():
            raise HTTPException(status_code=409, detail="Message ID already exists with different content")
        return resolve_message(request.message)


@app.post("/scan")
def scan_text(request: TextInput):
    require_synthetic(request.synthetic)
    return {"ok": True, "verdict": inspect(request.text).to_dict()}


@app.post("/analyze")
def analyze(request: TextInput):
    require_synthetic(request.synthetic)
    message = Message(id=f"msg_{uuid.uuid4().hex[:12]}", channel="chat", text=request.text,
                      sender="fictional_paste", timestamp=datetime.now(timezone.utc).isoformat())
    with store.LOCK:
        return resolve_message(message)


@app.get("/dna")
def dna_records():
    return {"ok": True, "dna_records": [ScamDNA.model_validate(item).model_dump() for item in store.all_records("dna")]}


@app.get("/graph")
def graph():
    return {"ok": True, "graph": cluster_and_graph(store.all_records("dna"))}


@app.post("/engage/start")
def engage_start(request: EngagementStart):
    with store.LOCK:
        message = Message.model_validate(required("messages", request.message_id))
        session = VictimSession.start(message.id)
        state = session.next_turn(message.text)
        store.put("engagements", state["session_id"], state)
        return {"ok": True, "session": state}


@app.post("/engage/step")
def engage_step(request: TrainingInput):
    require_synthetic(request.synthetic)
    with store.LOCK:
        session = VictimSession(required("engagements", request.session_id))
        state = session.next_turn(request.text)
        store.put("engagements", state["session_id"], state)
        return {"ok": True, "session": state}


@app.get("/engage/{session_id}")
def get_engagement(session_id: str):
    return {"ok": True, "session": required("engagements", session_id)}


@app.post("/train/start")
def train_start(request: TrainingStart):
    if not request.consent:
        raise ValueError("Training requires consent to a fictional drill")
    with store.LOCK:
        dna = ScamDNA.model_validate(required("dna", request.dna_id)).model_dump()
        session = ScammerPersona.start(dna, len(store.all_records("training")))
        store.put("training", session.state["session_id"], session.state)
        return {"ok": True, "session": session.state}


@app.post("/train/message")
def train_message(request: TrainingInput):
    require_synthetic(request.synthetic)
    with store.LOCK:
        session = ScammerPersona(required("training", request.session_id))
        state = session.reply(request.text)
        store.put("training", state["session_id"], state)
        return {"ok": True, "session": state}


@app.post("/train/end")
def train_end(request: SessionInput):
    with store.LOCK:
        state = required("training", request.session_id)
        if state.get("report"):
            return {"ok": True, "report": ImmunityReport.model_validate(state["report"]).model_dump()}
        # Persist the stop before scoring so a model failure cannot reopen a drill.
        state["status"] = "completed"
        store.put("training", request.session_id, state)
        report = score_session(state)
        state["report"] = report
        store.put("training", request.session_id, state)
        store.put("immunity", request.session_id, report)
        return {"ok": True, "report": report}


@app.get("/train/{session_id}")
def get_training(session_id: str):
    return {"ok": True, "session": required("training", session_id)}


@app.get("/immunity")
def immunity():
    return {"ok": True, "reports": [ImmunityReport.model_validate(item).model_dump() for item in store.all_records("immunity")]}
