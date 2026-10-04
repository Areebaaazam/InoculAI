import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DNA_FILE = DATA_DIR / "dna.json"
GRAPH_FILE = DATA_DIR / "graph.json"

def cluster_and_graph():
    records = _load_dna()
    if not records:
        _write_graph({"nodes": [], "edges": []})
        return
    campaigns = _build_campaigns(records)
    nodes = []
    edges = []
    for cid, camp in campaigns.items():
        nodes.append({"id": cid, "type": "campaign", "label": camp["label"],
                       "size": camp["size"], "scams": camp["scams"]})
        for ioc_type in ["phones", "domains", "wallets"]:
            for ioc in camp.get("iocs", {}).get(ioc_type, []):
                ioc_id = f"ioc_{ioc_type}_{ioc}"
                if not any(n["id"] == ioc_id for n in nodes):
                    nodes.append({"id": ioc_id, "type": ioc_type, "label": ioc, "size": 2})
                edges.append({"source": cid, "target": ioc_id})
    _write_graph({"nodes": nodes, "edges": edges})

def _build_campaigns(records):
    campaigns = {}
    used = set()
    for i, r1 in enumerate(records):
        if i in used:
            continue
        cid = f"camp_{len(campaigns) + 1:03d}"
        members = [r1]
        used.add(i)
        iocs1 = r1.get("iocs", {})
        t1 = r1.get("tactics", {})
        for j, r2 in enumerate(records):
            if j in used:
                continue
            iocs2 = r2.get("iocs", {})
            t2 = r2.get("tactics", {})
            if _same_campaign(iocs1, iocs2, t1, t2):
                members.append(r2)
                used.add(j)
        all_iocs = {"phones": [], "domains": [], "wallets": []}
        for m in members:
            for k in all_iocs:
                all_iocs[k].extend(m.get("iocs", {}).get(k, []))
        for k in all_iocs:
            all_iocs[k] = list(set(all_iocs[k]))
        campaigns[cid] = {
            "label": members[0].get("scam_type", "unknown").replace("_", " ").title(),
            "size": min(len(members) * 2, 10),
            "scams": len(members),
            "iocs": all_iocs,
        }
    return campaigns

def _same_campaign(iocs1, iocs2, t1, t2, threshold=15):
    for k in ["phones", "domains", "wallets"]:
        if set(iocs1.get(k, [])) & set(iocs2.get(k, [])):
            return True
    if t1 and t2:
        score = sum(abs(t1.get(k, 0) - t2.get(k, 0)) for k in t1)
        if score < threshold * 5:
            return True
    return False

def _load_dna():
    if not DNA_FILE.exists() or DNA_FILE.stat().st_size == 0:
        return []
    return json.loads(DNA_FILE.read_text(encoding="utf-8"))

def _write_graph(data):
    GRAPH_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")