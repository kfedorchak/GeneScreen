"""Literature-research agent (STUB).

Returns a mechanistic-support score + citations for a driver->dependency
relationship. A live version would search/read the literature; this stub derives
a plausible, deterministic signal from gene prominence and the relationship type.
"""
from __future__ import annotations

from ..schemas import Citation, LiteratureReport
from ._det import FAMOUS, unit


def get_report(
    driver: str, dependency: str, relationship: str, effect_size: float
) -> LiteratureReport:
    jitter = unit("lit", driver, dependency) * 0.2
    if relationship == "cis" and dependency in FAMOUS:
        base, note = 0.82, f"{dependency} amplification is an established oncogene-addiction dependency."
    elif dependency in FAMOUS or driver in FAMOUS:
        base, note = 0.45, f"Partial precedent linking {driver} amplification to {dependency} dependency."
    else:
        base, note = 0.15, f"No strong prior mechanistic link between {driver} and {dependency} found."
    support = min(0.97, base + jitter)

    # Illustrative, NON-real citations (url=None so the UI never renders a link
    # that could be mistaken for a genuine reference).
    citations: list[Citation] = []
    if support > 0.3:
        citations.append(
            Citation(
                title=f"[illustrative] {dependency} dependency in {driver}-amplified tumors",
                url=None,
                year=2019 + int(unit('yr', driver, dependency) * 6),
                snippet=f"Cells with elevated {driver} copy number showed increased sensitivity to {dependency} knockout.",
            )
        )
    if support > 0.6:
        citations.append(
            Citation(
                title=f"[illustrative] Synthetic-lethal interactions of the {driver} amplicon",
                url=None,
                year=2020 + int(unit('yr2', driver, dependency) * 5),
            )
        )

    return LiteratureReport(
        support_score=round(support, 3),
        summary=f"(simulated literature agent) {note}",
        citations=citations,
    )
