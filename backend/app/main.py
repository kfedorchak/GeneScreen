"""GeneScreen API.

Loads the demo DepMap subset once at startup and exposes the analysis engine:
  GET  /api/dataset      dataset shape + available lineages
  POST /api/screen       run a screen (ScreenParams) -> ranked candidates
  GET  /api/pair_detail  per-line CN vs gene-effect scatter for the dossier plot

The built React app (backend/app/static) is served at / for single-deploy.
"""
from __future__ import annotations

import math
import os
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .agents import orchestrator
from .analysis import engine, filters, scoring
from .data import loader
from .schemas import CandidatePair, ScreenParams

# Number of top candidates whose agent scores (targetability/bio-support/novelty)
# are computed and folded into the composite at screen time. The rest stay
# neutral until opened in the dossier.
ENRICH_N = 40

app = FastAPI(title="GeneScreen", version="0.1.0")

# Same-origin in production (FastAPI serves the SPA), so no cross-origin access is
# needed by default. Open it explicitly via GENESCREEN_ALLOWED_ORIGINS if hosting
# the frontend on a separate domain.
_ALLOWED = [o.strip() for o in os.getenv("GENESCREEN_ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=_ALLOWED, allow_methods=["*"], allow_headers=["*"]
)

# Lightweight per-IP sliding-window rate limit on the compute-heavy endpoints, so
# a public URL can't be trivially hammered. Tunable via env.
_RATE_MAX = int(os.getenv("GENESCREEN_RATE_MAX", "40"))
_RATE_WINDOW = int(os.getenv("GENESCREEN_RATE_WINDOW", "60"))
_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request) -> None:
    fwd = request.headers.get("x-forwarded-for", "")
    ip = fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")
    now = time.time()
    q = _hits[ip]
    while q and q[0] < now - _RATE_WINDOW:
        q.popleft()
    if len(q) >= _RATE_MAX:
        raise HTTPException(429, "Rate limit exceeded — please slow down.")
    q.append(now)

# Load the bundled dataset once; align/normalize for pair lookups.
DATASET = loader.load_demo_subset()
_A_ALIGNED, _B_ALIGNED = filters.align(DATASET.A, DATASET.B)


# --------------------------------------------------------------------------- #
# NaN-safe scalar coercion (JSON can't carry NaN)
# --------------------------------------------------------------------------- #
def _f(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def _i(v):
    f = _f(v)
    return None if f is None else int(f)


def _s(v):
    if v is None:
        return None
    try:
        if isinstance(v, float) and math.isnan(v):
            return None
    except TypeError:
        pass
    s = str(v)
    return None if s in ("nan", "None", "") else s


# --------------------------------------------------------------------------- #
# endpoints
# --------------------------------------------------------------------------- #
@app.get("/api/dataset")
def dataset_info():
    meta = DATASET.model_meta
    lineages = (
        sorted(meta["OncotreeLineage"].dropna().unique().tolist())
        if meta is not None and "OncotreeLineage" in meta.columns
        else []
    )
    return {
        "source": DATASET.source,
        "n_lines": int(len(_A_ALIGNED.index)),
        "n_drivers": int(DATASET.A.shape[1]),
        "n_dependencies": int(DATASET.B.shape[1]),
        "n_common_essentials": len(DATASET.common_essentials),
        "n_lineages": len(lineages),
        "lineages": lineages,
    }


def _to_candidate(r) -> CandidatePair:
    cs = r.get("component_scores") if hasattr(r, "get") else None
    cs = cs or {}
    return CandidatePair(
        driver_gene=str(r["driver_gene"]),
        dependency_gene=str(r["dependency_gene"]),
        relationship=str(r["relationship"]),
        n=_i(r["n"]) or 0,
        effect_metric=str(r["effect_metric"]),
        effect_size=_f(r["effect_size"]) or 0.0,
        slope=_f(r.get("slope")),
        p_value=_f(r["p_value"]) or 1.0,
        q_value=_f(r["q_value"]) or 1.0,
        amp_frequency=_f(r["amp_frequency"]) or 0.0,
        dep_selectivity=_f(r["dep_selectivity"]) or 0.0,
        frac_dependent=_f(r["frac_dependent"]) or 0.0,
        cn_correlation=_f(r.get("cn_correlation")),
        module_label=_s(r.get("module_label")),
        module_size=_i(r.get("module_size")),
        module_members=_s(r.get("module_members")),
        n_module_drivers=_i(r.get("n_module_drivers")),
        component_scores={k: float(v) for k, v in cs.items()},
        composite_score=_f(r.get("composite_score")),
    )


@app.post("/api/screen")
def screen(params: ScreenParams, _: None = Depends(rate_limit)):
    res = engine.run_screen(
        DATASET.A, DATASET.B, params, DATASET.model_meta, DATASET.common_essentials
    )
    meta = {
        "mode": params.mode.value,
        "direction": params.direction.value,
        "n_significant": int(len(res)),
        "collapsed": bool(params.collapse_amplicons),
    }
    if res.empty:
        return {"meta": meta, "candidates": []}

    # First pass with neutral agent scores to rank, then enrich the top N with
    # real targetability (Open Targets) + stubbed bio-support/novelty and re-score.
    scored = scoring.composite_score(res)
    top = scored.head(ENRICH_N)
    agent_scores = orchestrator.agent_score_series(top, scored.index)
    scored = scoring.composite_score(scored, agent_scores=agent_scores)

    candidates = [_to_candidate(row) for _, row in scored.iterrows()]
    meta["n_returned"] = len(candidates)
    meta["n_enriched"] = int(len(top))
    meta["n_cis"] = int((scored["relationship"] == "cis").sum())
    meta["n_trans"] = int((scored["relationship"] == "trans").sum())
    return {"meta": meta, "candidates": candidates}


@app.get("/api/dossier")
def dossier(
    driver: str,
    dependency: str,
    relationship: str = "trans",
    effect_size: float = 0.0,
    _: None = Depends(rate_limit),
):
    """Full per-candidate agent dossier (literature, precedent, targetability, molecular)."""
    return orchestrator.reports(driver, dependency, relationship, effect_size)


@app.get("/api/pair_detail")
def pair_detail(driver: str, dependency: str):
    if driver not in _A_ALIGNED.columns:
        raise HTTPException(404, f"driver {driver!r} not in copy-number panel")
    if dependency not in _B_ALIGNED.columns:
        raise HTTPException(404, f"dependency {dependency!r} not in dependency panel")

    cn = _A_ALIGNED[driver]
    ge = _B_ALIGNED[dependency]
    meta = DATASET.model_meta
    lin = (
        meta["OncotreeLineage"].reindex(_A_ALIGNED.index)
        if meta is not None and "OncotreeLineage" in meta.columns
        else None
    )
    points = []
    for line in _A_ALIGNED.index:
        c, e = cn.get(line), ge.get(line)
        if c is None or e is None or math.isnan(float(c)) or math.isnan(float(e)):
            continue
        points.append(
            {
                "line": str(line),
                "cn": float(c),
                "effect": float(e),
                "lineage": (str(lin.get(line)) if lin is not None and _s(lin.get(line)) else "Unknown"),
            }
        )
    return {"driver": driver, "dependency": dependency, "points": points}


# --------------------------------------------------------------------------- #
# static React build (single-deploy). Mounted last so /api/* wins.
# --------------------------------------------------------------------------- #
_STATIC = Path(__file__).parent / "static"
if _STATIC.exists():
    app.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")
