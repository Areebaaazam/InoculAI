"""Local campaign similarity over canonical tactic vectors and inert IOCs."""

import math

from sentinel import TACTICS
from .contracts import ScamDNA


def similarity(first: dict, second: dict) -> float:
    a, b = first["tactics"], second["tactics"]
    magnitude = math.sqrt(sum(a[t] ** 2 for t in TACTICS) * sum(b[t] ** 2 for t in TACTICS))
    return sum(a[t] * b[t] for t in TACTICS) / magnitude if magnitude else 0.0


def assign_campaign(dna: dict, records: list[dict]) -> dict:
    records = [ScamDNA.model_validate(record).model_dump() for record in records if record["id"] != dna["id"]]
    if records:
        match = max(records, key=lambda record: similarity(dna, record))
        score = min(1.0, max(0.0, similarity(dna, match)))
        dna["similarity"] = round(score, 4)
        if score >= 0.85:
            dna["campaign_id"] = match["campaign_id"]
    return ScamDNA.model_validate(dna).model_dump()


def cluster_and_graph(records: list[dict]) -> dict:
    nodes, edges, seen = [], [], set()
    for record in records:
        dna = ScamDNA.model_validate(record)
        if dna.campaign_id not in seen:
            nodes.append({"id": dna.campaign_id, "type": "campaign", "label": dna.campaign_id})
            seen.add(dna.campaign_id)
        nodes.append({"id": dna.id, "type": "dna", "label": dna.id})
        edges.append({"source": dna.campaign_id, "target": dna.id})
        for group, values in dna.iocs.model_dump().items():
            for value in values:
                record_id = f"{group}:{value}"
                if record_id not in seen:
                    nodes.append({"id": record_id, "type": group, "label": value})
                    seen.add(record_id)
                edges.append({"source": dna.id, "target": record_id})
    return {"nodes": nodes, "edges": edges}
