"""Precedent agent (STUB).

Judges whether the dependency target / relationship is novel white-space or a
crowded, well-trodden program. Feeds the novelty score (which the user can rank
up for discovery or down for de-risking).
"""
from __future__ import annotations

from ..schemas import PrecedentReport
from ._det import DRUGGED, FAMOUS, unit


def get_report(driver: str, dependency: str, relationship: str) -> PrecedentReport:
    jitter = unit("prec", driver, dependency) * 0.15
    if dependency in DRUGGED:
        novelty, status = 0.15 + jitter, "crowded"
        summary = f"{dependency} is a well-precedented target with approved/clinical programs."
        programs = [f"{dependency} inhibitor (approved)", f"{dependency} program (Phase 2)"]
    elif dependency in FAMOUS:
        novelty, status = 0.5 + jitter, "emerging"
        summary = f"{dependency} has emerging interest but few disclosed programs in this context."
        programs = [f"{dependency} tool compound (preclinical)"]
    else:
        novelty, status = min(0.97, 0.8 + jitter), "novel"
        summary = f"No disclosed programs pursuing {dependency} as a dependency of {driver} amplification — white space."
        programs = []

    return PrecedentReport(
        novelty_score=round(min(0.97, novelty), 3),
        status=status,  # type: ignore[arg-type]
        summary=f"(simulated precedent agent) {summary}",
        programs=programs,
    )
