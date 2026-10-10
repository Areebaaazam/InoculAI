"""The context.md contracts are validated at every application boundary."""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator

from sentinel import TACTICS, validate_text

DISCLAIMER = "Training metric, not a scientifically validated probability of avoiding a real-world scam."


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class TacticScores(Contract):
    urgency: StrictInt = Field(ge=0, le=100)
    fear: StrictInt = Field(ge=0, le=100)
    authority: StrictInt = Field(ge=0, le=100)
    reward: StrictInt = Field(ge=0, le=100)
    trust: StrictInt = Field(ge=0, le=100)
    payment_pressure: StrictInt = Field(ge=0, le=100)


class Indicators(Contract):
    phones: list[StrictStr]
    domains: list[StrictStr]
    wallets: list[StrictStr]
    payment_links: list[StrictStr]


def iso_timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return value


class Message(Contract):
    id: StrictStr = Field(min_length=1, max_length=100)
    channel: Literal["sms", "email", "chat"]
    text: StrictStr
    sender: StrictStr = Field(min_length=1, max_length=100)
    timestamp: StrictStr

    _text = field_validator("text")(validate_text)
    _timestamp = field_validator("timestamp")(iso_timestamp)


class ScamDNA(Contract):
    id: StrictStr = Field(min_length=1)
    source_message_id: StrictStr = Field(min_length=1)
    tactics: TacticScores
    attack_chain: list[StrictStr] = Field(min_length=1, max_length=7)
    iocs: Indicators
    campaign_id: StrictStr = Field(min_length=1)
    similarity: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    extraction_model: StrictStr = Field(min_length=1)
    created_at: StrictStr

    _timestamp = field_validator("created_at")(iso_timestamp)

    @field_validator("attack_chain")
    @classmethod
    def valid_chain(cls, chain):
        if len(set(chain)) != len(chain) or any(stage not in (*TACTICS, "action") for stage in chain):
            raise ValueError("attack_chain contains duplicate or unknown stages")
        return chain


class Score(Contract):
    tactic: Literal["urgency", "fear", "authority", "reward", "trust", "payment_pressure"]
    result: Literal["strong", "medium", "weak"]
    note: StrictStr = Field(min_length=1, max_length=400)


class FailMoment(Contract):
    tactic: Literal["urgency", "fear", "authority", "reward", "trust", "payment_pressure"]
    result: Literal["strong", "medium", "weak"]
    text: StrictStr = Field(min_length=1, max_length=1000)


class ImmunityReport(Contract):
    user_session: StrictStr = Field(min_length=1)
    trained_on: StrictStr = Field(min_length=1)
    variant_id: StrictStr = Field(min_length=1)
    scores: list[Score] = Field(min_length=1, max_length=6)
    immunity_score: StrictInt = Field(ge=0, le=100)
    disclaimer: Literal[DISCLAIMER]
    coaching: list[StrictStr] = Field(min_length=1)
    fail_moment: FailMoment | None = None

    @field_validator("scores")
    @classmethod
    def unique_scores(cls, rows):
        if len({row.tactic for row in rows}) != len(rows):
            raise ValueError("score tactics must be unique")
        return rows

    @field_validator("coaching")
    @classmethod
    def readable_coaching(cls, lines):
        if any(not line.strip() for line in lines):
            raise ValueError("coaching lines must be non-empty")
        return lines


class TextInput(Contract):
    text: StrictStr
    synthetic: StrictBool
    _text = field_validator("text")(validate_text)


class TrainingInput(TextInput):
    session_id: StrictStr


class SessionInput(Contract):
    session_id: StrictStr


class TrainingStart(Contract):
    dna_id: StrictStr
    consent: StrictBool


class EngagementStart(Contract):
    message_id: StrictStr


WALLET_IDENTIFIER = re.compile(r"\b0x[a-f0-9]{40}\b", re.I)
PHONE_CANDIDATE = re.compile(r"\b\d[0-9 -]{5,30}\d\b")
OUTBOUND = re.compile(r"https?://|\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|xyz|top)\b", re.I)
SECRET_ASK = re.compile(r"\b(?:send|share|enter|give|provide)\b[^.!?\n]{0,50}\b(?:password|OTP|PIN|card number|verification code|private key)\b", re.I)


def has_phone_like_identifier(text: str) -> bool:
    for match in PHONE_CANDIDATE.finditer(text):
        digits = sum(char.isdigit() for char in match.group(0))
        if 7 <= digits <= 19:
            return True
    return False


def has_email_like_identifier(text: str) -> bool:
    for token in text.split():
        if token.count("@") != 1:
            continue
        local, domain = token.strip(".,;:!?()[]{}<>\"'").split("@", 1)
        if not local or not domain or "." not in domain:
            continue
        if local[-1] == "." or domain[0] == "." or domain[-1] == ".":
            continue
        return True
    return False


def has_pii_like_identifier(text: str) -> bool:
    return WALLET_IDENTIFIER.search(text) is not None or has_phone_like_identifier(text) or has_email_like_identifier(text)


def safe_training_input(text: str) -> str:
    validate_text(text)
    if has_pii_like_identifier(text) or OUTBOUND.search(text):
        raise ValueError("Use fictional text and training markers; real contacts, identifiers and links are rejected")
    return text


def safe_agent_reply(reply: str, *, victim: bool = False) -> str:
    validate_text(reply)
    if len(reply) > 900 or has_pii_like_identifier(reply) or OUTBOUND.search(reply) or SECRET_ASK.search(reply):
        raise ValueError("generated reply violates the synthetic sandbox")
    if victim and re.search(r"\bI(?:'ve| have)?\s+(?:sent|paid|transferred|clicked|opened|downloaded|logged in)\b", reply, re.I):
        raise ValueError("victim may not claim an external action")
    return reply
