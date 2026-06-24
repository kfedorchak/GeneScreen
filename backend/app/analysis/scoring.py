"""Composite ranking.

The composite score is a transparent, tunable weighted sum of 0-1 component
scores. Statistical components are always available; agent/targetability
components default to neutral (0.5) until those agents are wired in, so the same
function works in phase 1 and after the agents land.

Components
----------
effect       magnitude of the induced dependency (|effect_size|)
confidence   statistical confidence (-log10 q, squashed)
selectivity  is the dependency selective rather than pan-essential?
prevalence   how often the driver is amplified (addressable population)
targetability  Open Targets tractability of the dependency gene   [agent]
bio_support  known mechanistic support for the relationship        [agent]
novelty      white-space vs crowded (sign set by user preference)  [agent]

`novelty_preference` lets the user rank novel targets up (+1, discovery) or down
(-1, de-risking); 0 ignores novelty.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_WEIGHTS: dict[str, float] = {
    "effect": 0.30,
    "confidence": 0.20,
    "selectivity": 0.15,
    "prevalence": 0.10,
    "targetability": 0.15,
    "bio_support": 0.05,
    "novelty": 0.05,
}

_STAT_COMPONENTS = {"effect", "confidence", "selectivity", "prevalence"}
_AGENT_COMPONENTS = {"targetability", "bio_support", "novelty"}


def _minmax(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    lo, hi = s.min(), s.max()
    if not np.isfinite(lo) or not np.isfinite(hi) or hi - lo < 1e-12:
        return pd.Series(0.5, index=s.index)
    return (s - lo) / (hi - lo)


def _selectivity_score(res: pd.DataFrame) -> pd.Series:
    """Reward dependencies that are essential in *some* lines, not all/none.

    Peaks when ~30% of lines are dependent and the gene effect spreads widely.
    """
    frac = res["frac_dependent"].astype(float).clip(0, 1)
    sweet = 1.0 - (frac - 0.30).abs() / 0.70           # triangular peak at 0.30
    spread = _minmax(res["dep_selectivity"])
    return (0.5 * sweet.clip(0, 1) + 0.5 * spread).clip(0, 1)


def compute_components(res: pd.DataFrame) -> pd.DataFrame:
    """Add the always-available statistical 0-1 component scores."""
    res = res.copy()
    res["score_effect"] = _minmax(res["effect_size"].abs())
    conf = -np.log10(res["q_value"].clip(lower=1e-300))
    res["score_confidence"] = _minmax(conf)
    res["score_selectivity"] = _selectivity_score(res)
    res["score_prevalence"] = res["amp_frequency"].astype(float).clip(0, 1)
    return res


def composite_score(
    res: pd.DataFrame,
    weights: dict[str, float] | None = None,
    novelty_preference: float = 1.0,
    agent_scores: dict[str, pd.Series] | None = None,
) -> pd.DataFrame:
    """Attach component + composite scores. Re-runnable cheaply for live re-ranking.

    agent_scores: optional {"targetability"|"bio_support"|"novelty": Series} keyed
    like res.index; missing agent components default to neutral 0.5.
    """
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    agent_scores = agent_scores or {}

    if "score_effect" not in res.columns:
        res = compute_components(res)
    res = res.copy()

    for comp in _AGENT_COMPONENTS:
        col = f"score_{comp}"
        if comp in agent_scores:
            res[col] = agent_scores[comp].reindex(res.index).astype(float).fillna(0.5)
        else:
            res[col] = 0.5

    # novelty preference flips the contribution direction around the neutral point
    res["score_novelty"] = 0.5 + novelty_preference * (res["score_novelty"] - 0.5)

    total_w = sum(weights.values()) or 1.0
    composite = sum(
        weights[c] * res[f"score_{c}"] for c in DEFAULT_WEIGHTS
    ) / total_w
    res["composite_score"] = composite.clip(0, 1)

    # stash components as a dict column for the API/schema
    comp_cols = [f"score_{c}" for c in DEFAULT_WEIGHTS]
    res["component_scores"] = res[comp_cols].rename(
        columns=lambda c: c.replace("score_", "")
    ).to_dict(orient="records")

    return res.sort_values("composite_score", ascending=False).reset_index(drop=True)
