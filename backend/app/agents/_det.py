"""Deterministic pseudo-values from a string seed.

The stub agents must be reproducible (same pair -> same output) without a live
model, so we derive stable 0-1 jitter from a hash rather than RNG.
"""
from __future__ import annotations

import hashlib

# Genes with well-known oncogene-addiction / drug-discovery footprints. Used to
# make the stubs' signals plausible rather than uniform.
FAMOUS = frozenset({
    "ERBB2", "MYC", "MYCN", "EGFR", "KRAS", "BRAF", "MET", "CCND1", "CCNE1",
    "CDK4", "CDK6", "CDK2", "MDM2", "MDM4", "PIK3CA", "AKT1", "AKT2", "FGFR1",
    "FGFR2", "MCL1", "BCL2L1", "AR", "AURKA", "KIT", "PDGFRA", "IGF1R", "TERT",
})
# Genes with approved/clinical small-molecule or antibody programs (crowded).
DRUGGED = frozenset({
    "ERBB2", "EGFR", "CDK4", "CDK6", "MET", "BRAF", "AR", "MCL1", "BCL2L1",
    "PIK3CA", "AKT1", "FGFR1", "FGFR2", "AURKA", "CDK2", "KIT", "PDGFRA", "IGF1R",
})


def unit(*parts: str) -> float:
    """Stable float in [0,1) from the given seed parts."""
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return (int(h[:8], 16) % 10_000) / 10_000.0
