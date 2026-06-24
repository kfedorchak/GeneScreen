"""Fan a candidate out to the agents and assemble results.

`reports()` builds the full per-candidate dossier (all four agents) for the
/api/dossier endpoint. `agent_score_series()` computes the agent-derived 0-1
score components for a set of top candidates so they feed the composite ranking;
candidates outside that set keep the neutral 0.5 default.
"""
from __future__ import annotations

import pandas as pd

from . import literature, molecular, precedent, targetability


def reports(driver: str, dependency: str, relationship: str, effect_size: float) -> dict:
    tgt = targetability.get_report(dependency)
    return {
        "literature": literature.get_report(driver, dependency, relationship, effect_size),
        "precedent": precedent.get_report(driver, dependency, relationship),
        "targetability": tgt,
        "molecular": molecular.get_report(dependency, targetability=tgt.targetability_score),
    }


def agent_score_series(
    top_rows: pd.DataFrame, full_index: pd.Index, allow_live: bool | None = None
) -> dict[str, pd.Series]:
    """0-1 agent score components for the top candidates, aligned to full_index."""
    tgt = pd.Series(index=full_index, dtype=float)
    bio = pd.Series(index=full_index, dtype=float)
    nov = pd.Series(index=full_index, dtype=float)
    for idx, r in top_rows.iterrows():
        drv, dep, rel = r["driver_gene"], r["dependency_gene"], r["relationship"]
        eff = float(r["effect_size"])
        tgt.at[idx] = targetability.score(dep, allow_live=allow_live)
        bio.at[idx] = literature.get_report(drv, dep, rel, eff).support_score
        nov.at[idx] = precedent.get_report(drv, dep, rel).novelty_score
    return {"targetability": tgt, "bio_support": bio, "novelty": nov}
