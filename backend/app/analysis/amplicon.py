"""Driver-side amplicon clustering.

When several drivers sit on the same amplicon their copy-number profiles are
near-identical, so each produces a virtually identical association with a given
dependency — e.g. a 20q cluster (AHCY, DYNLRB1, CHMP4B, ...) all pointing at
UFM1. They are statistically indistinguishable (collinear CN), so reporting them
as separate discoveries is misleading.

We group drivers whose CN profiles are tightly correlated into **amplicon
modules** (connected components of the thresholded CN-correlation graph) and
collapse each (module, dependency) down to one representative row that lists the
co-amplified members. This complements the dependency-side co-amplification
control in engine.py: that one removes passengers of a cis-addicted *dependency*;
this one de-duplicates co-amplified *drivers*.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components


# Prefer a recognizable oncogene as a module's lead label when one is present,
# so "CCND1 +53" surfaces instead of an arbitrary high-variance passenger.
CANONICAL_ONCOGENES = frozenset({
    "ERBB2", "MYC", "MYCN", "MYCL", "EGFR", "KRAS", "MET", "CCND1", "CCNE1",
    "CDK4", "CDK6", "MDM2", "MDM4", "FGFR1", "FGFR2", "AR", "BCL2L1", "MCL1",
    "TERT", "SOX2", "KIT", "PDGFRA", "AKT1", "AKT2", "PIK3CA", "NKX2-1",
    "YAP1", "CCND2", "CDK2", "AURKA", "BRAF", "IGF1R", "ZNF217", "GATA6",
})


@dataclass
class AmpliconModules:
    gene_to_module: dict[str, int]
    members: dict[int, list[str]]
    label: dict[int, str]

    def size(self, module_id: int) -> int:
        return len(self.members[module_id])


def _rank_unit(M: np.ndarray) -> np.ndarray:
    R = np.apply_along_axis(stats.rankdata, 0, M)
    R = R - R.mean(axis=0, keepdims=True)
    norms = np.linalg.norm(R, axis=0, keepdims=True)
    norms[norms == 0] = 1.0
    return R / norms


def cluster_drivers(A: pd.DataFrame, threshold: float = 0.7) -> AmpliconModules:
    """Group drivers into amplicon modules by CN-profile correlation.

    Two drivers are linked when corr(CN) >= threshold; modules are connected
    components, so a singleton driver forms its own module.
    """
    genes = list(A.columns)
    R = _rank_unit(A.fillna(A.mean()).to_numpy(dtype=float))
    corr = R.T @ R
    np.fill_diagonal(corr, 0.0)
    adj = csr_matrix(corr >= threshold)
    _, labels = connected_components(adj, directed=False)

    members: dict[int, list[str]] = {}
    for g, lab in zip(genes, labels):
        members.setdefault(int(lab), []).append(g)

    stds = A.std().to_dict()
    label: dict[int, str] = {}
    for lab, ms in members.items():
        # lead = a canonical oncogene if the module has one, else the most
        # variable (most driver-like) member.
        onco = [g for g in ms if g in CANONICAL_ONCOGENES]
        pool = onco or ms
        lead = max(pool, key=lambda g: stds.get(g, 0.0))
        label[lab] = lead if len(ms) == 1 else f"{lead} +{len(ms) - 1}"

    gene_to_module = {g: int(lab) for g, lab in zip(genes, labels)}
    return AmpliconModules(gene_to_module, members, label)


def collapse(res: pd.DataFrame, mods: AmpliconModules) -> pd.DataFrame:
    """Collapse each (amplicon module, dependency) to one representative row.

    The representative is the module member with the strongest evidence (smallest
    q, then largest |effect|). Adds module annotations; singleton modules pass
    through unchanged (one row each).
    """
    if res.empty:
        return res
    res = res.copy()
    res["module_id"] = res["driver_gene"].map(mods.gene_to_module)
    res["module_label"] = res["module_id"].map(mods.label)
    res["module_size"] = res["module_id"].map(lambda m: mods.size(m))

    res["_abseff"] = res["effect_size"].abs()
    # Representative = strongest evidence (smallest p, largest |effect|), but
    # prefer the true same-gene cis row when the group has one, so a cis-amplicon
    # group shows e.g. CCND1->CCND1 rather than a co-amplified passenger. Ordered
    # by p (not q) because this runs BEFORE FDR; p and q are rank-equivalent.
    sort_cols, ascending = ["p_value", "_abseff"], [True, False]
    if "same_gene" in res.columns:
        res["_notsame"] = ~res["same_gene"].astype(bool)
        sort_cols, ascending = ["_notsame", *sort_cols], [True, *ascending]
    res = res.sort_values(sort_cols, ascending=ascending)

    grp = res.groupby(["module_id", "dependency_gene"], sort=False)
    res["n_module_drivers"] = grp["driver_gene"].transform("nunique")
    res["module_members"] = grp["driver_gene"].transform(
        lambda s: ", ".join(sorted(s.unique()))
    )
    rep = res.drop_duplicates(["module_id", "dependency_gene"], keep="first")
    return rep.drop(columns=[c for c in ("_abseff", "_notsame") if c in rep.columns]).reset_index(drop=True)
