"""Molecular-design agent (STUB).

Proposes chemotypes and a feasibility estimate for drugging the dependency gene.
A live version would call a generative design model; this stub derives a stable,
plausible signal, nudged by Open Targets targetability when available.
"""
from __future__ import annotations

from ..schemas import MolecularReport
from ._det import DRUGGED, unit

_CHEMOTYPES = [
    "ATP-competitive kinase inhibitor",
    "allosteric pocket binder",
    "molecular-glue degrader",
    "covalent warhead (Cys)",
    "macrocyclic PPI inhibitor",
    "PROTAC (CRBN)",
]


def get_report(dependency: str, targetability: float | None = None) -> MolecularReport:
    j = unit("mol", dependency)
    base = 0.65 if dependency in DRUGGED else 0.3 + j * 0.4
    if targetability is not None:
        base = 0.5 * base + 0.5 * targetability
    feasibility = round(min(0.97, base), 3)

    n = 1 + int(unit("nchem", dependency) * 2)  # 1-2 chemotypes
    start = int(unit("chem", dependency) * len(_CHEMOTYPES))
    chemotypes = [_CHEMOTYPES[(start + i) % len(_CHEMOTYPES)] for i in range(n)]

    return MolecularReport(
        feasibility_score=feasibility,
        summary=f"(simulated molecular-design agent) Proposed entry points for {dependency}.",
        proposed_chemotypes=chemotypes,
    )
