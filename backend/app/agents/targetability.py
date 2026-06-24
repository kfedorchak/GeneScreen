"""Targetability agent — LIVE Open Targets Platform tractability.

Resolves an HGNC symbol to an Ensembl gene id, pulls the `tractability` buckets,
and maps them to a 0-1 targetability score (best passed bucket across modalities).
Results are cached to disk so the demo is instant and we don't hammer the API
(Open Targets asks callers not to loop it one entity at a time).
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import httpx

from ..schemas import TargetabilityReport, TractabilityBucket

OT_ENDPOINT = "https://api.platform.opentargets.org/api/v4/graphql"
CACHE_PATH = Path(__file__).parents[1] / "data" / "targetability_cache.json"

_SEARCH_Q = (
    "query($q:String!){search(queryString:$q,entityNames:[\"target\"])"
    "{hits{id object{... on Target{approvedSymbol}}}}}"
)
_TRACT_Q = (
    "query($e:String!){target(ensemblId:$e){approvedSymbol "
    "tractability{label modality value}}}"
)

# Best-passed-bucket score per modality. Higher = more clinically de-risked.
_TIERS: dict[str, float] = {
    "Approved Drug": 1.0,
    "Advanced Clinical": 0.85,
    "Phase 1 Clinical": 0.7,
    "Structure with Ligand": 0.6,
    "High-Quality Ligand": 0.55,
    "High-Quality Pocket": 0.45,
    "Med-Quality Pocket": 0.35,
    "Druggable Family": 0.3,
    "UniProt loc high conf": 0.5,
    "GO CC high conf": 0.45,
    "UniProt loc med conf": 0.35,
    "Human Protein Atlas loc": 0.3,
    "UniProt SigP or TMHMM": 0.3,
    "Literature": 0.4,
    "UniProt Ubiquitination": 0.35,
    "Database Ubiquitination": 0.3,
    "Half-life Data": 0.25,
    "Small Molecule Binder": 0.4,
}
_MODALITY_NAME = {"SM": "small molecule", "AB": "antibody", "PR": "PROTAC", "OC": "other"}

# Live API calls are opt-in (cache covers the whole demo subset). Off by default
# so a public /api/dossier with arbitrary gene params can't trigger outbound
# calls. Enable for local dev / uploads with GENESCREEN_ALLOW_LIVE_OT=1.
_ALLOW_LIVE = os.getenv("GENESCREEN_ALLOW_LIVE_OT", "0") == "1"

_lock = threading.Lock()
_cache: dict | None = None


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        _cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    return _cache


def _save_cache() -> None:
    with _lock:
        CACHE_PATH.write_text(json.dumps(_cache))


def fetch_live(gene: str, timeout: float = 20.0) -> dict:
    """Hit Open Targets. Returns {ensembl_id, buckets:[{label,modality,value}]}."""
    with httpx.Client(timeout=timeout) as client:
        r = client.post(OT_ENDPOINT, json={"query": _SEARCH_Q, "variables": {"q": gene}})
        r.raise_for_status()
        hits = (r.json().get("data") or {}).get("search", {}).get("hits", []) or []
        ensembl = None
        for h in hits:
            sym = ((h.get("object") or {}).get("approvedSymbol") or "").upper()
            if sym == gene.upper():
                ensembl = h["id"]
                break
        if ensembl is None and hits:
            ensembl = hits[0]["id"]
        if ensembl is None:
            return {"ensembl_id": None, "buckets": []}

        r2 = client.post(OT_ENDPOINT, json={"query": _TRACT_Q, "variables": {"e": ensembl}})
        r2.raise_for_status()
        tg = (r2.json().get("data") or {}).get("target") or {}
        buckets = tg.get("tractability") or []
        return {"ensembl_id": ensembl, "buckets": buckets}


def _score(buckets: list[dict]) -> tuple[float, str | None]:
    """Best passed-bucket tier across modalities -> (score, top_modality)."""
    best, best_mod = 0.0, None
    for b in buckets:
        if not b.get("value"):
            continue
        tier = _TIERS.get(b.get("label", ""), 0.2)
        if tier > best:
            best, best_mod = tier, b.get("modality")
    if not buckets:
        return 0.3, None  # unknown
    if best == 0.0:
        return 0.1, None  # assessed, nothing passed -> hard target
    return best, _MODALITY_NAME.get(best_mod or "", best_mod)


def get_report(gene: str, allow_live: bool | None = None) -> TargetabilityReport:
    if allow_live is None:
        allow_live = _ALLOW_LIVE
    cache = _load_cache()
    key = gene.upper()
    data = cache.get(key)
    if data is None and allow_live:
        try:
            data = fetch_live(gene)
            cache[key] = data
            _save_cache()
        except Exception:
            data = None
    if data is None:
        return TargetabilityReport(targetability_score=0.3, top_modality=None, buckets=[])

    buckets = [
        TractabilityBucket(label=b["label"], modality=b["modality"], value=bool(b["value"]))
        for b in data.get("buckets", [])
        if b.get("modality") in ("SM", "AB", "PR", "OC")
    ]
    score, top_modality = _score(data.get("buckets", []))
    return TargetabilityReport(
        ensembl_id=data.get("ensembl_id"),
        targetability_score=round(score, 3),
        top_modality=top_modality,
        buckets=buckets,
    )


def score(gene: str, allow_live: bool | None = None) -> float:
    return get_report(gene, allow_live=allow_live).targetability_score
