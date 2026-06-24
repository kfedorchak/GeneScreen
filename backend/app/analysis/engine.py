"""The A x B screen.

Given a copy-number matrix A (lines x genes, log2(relative_CN + 1), diploid=1.0)
and a CRISPR gene-effect matrix B (lines x genes, Chronos; 0 = no effect,
negative = dependency), find driver(A) -> dependency(B) relationships where the
driver's copy number associates with the dependency's essentiality.

Two modes:
  * continuous: Spearman correlation of CN vs gene effect across lines, optionally
    partialling out cancer lineage. Fully vectorised as a single matrix product.
  * binary: split lines into amplified / not-amplified for each driver, then a
    Mann-Whitney U test on each dependency's gene effect between the two groups.

We surface relationships where higher copy number tracks with *stronger*
dependency (more negative gene effect) -> a negative effect_size. Multiple
testing is controlled with Benjamini-Hochberg across every pair tested.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

from ..schemas import CoampHandling, Direction, Mode, Relationship, ScreenParams
from . import amplicon, filters


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _rankdata_columns(M: np.ndarray) -> np.ndarray:
    """Rank-transform each column independently (average ranks for ties)."""
    return np.apply_along_axis(stats.rankdata, 0, M)


def _unit_columns(M: np.ndarray) -> np.ndarray:
    """Center each column and scale to unit L2 norm. Zero-variance cols -> 0."""
    M = M - M.mean(axis=0, keepdims=True)
    norms = np.linalg.norm(M, axis=0, keepdims=True)
    norms[norms == 0] = 1.0
    return M / norms


def _residualize(M: np.ndarray, design: np.ndarray) -> np.ndarray:
    """Regress each column of M on `design` and return residuals (lineage adjust)."""
    # least-squares projection: resid = M - design @ (design^+ @ M)
    beta, *_ = np.linalg.lstsq(design, M, rcond=None)
    return M - design @ beta


def _lineage_design(model_meta: pd.DataFrame, index: pd.Index) -> np.ndarray | None:
    """One-hot lineage design matrix (with intercept) aligned to `index`."""
    if model_meta is None or "OncotreeLineage" not in model_meta.columns:
        return None
    lin = model_meta["OncotreeLineage"].reindex(index).fillna("Unknown")
    dummies = pd.get_dummies(lin, drop_first=False).to_numpy(dtype=float)
    intercept = np.ones((dummies.shape[0], 1))
    return np.hstack([intercept, dummies])


# --------------------------------------------------------------------------- #
# continuous mode
# --------------------------------------------------------------------------- #
def _run_continuous(
    A: pd.DataFrame, B: pd.DataFrame, params: ScreenParams, model_meta: pd.DataFrame | None
) -> pd.DataFrame:
    n = len(A)
    a_genes, b_genes = list(A.columns), list(B.columns)

    # Spearman == Pearson on ranks. Mean-impute NaNs per column before ranking
    # so the matrix product is well-defined (imputed cells sit at the column
    # center and contribute ~0 to the correlation).
    Ar = _rankdata_columns(A.fillna(A.mean()).to_numpy(dtype=float))
    Br = _rankdata_columns(B.fillna(B.mean()).to_numpy(dtype=float))

    if params.lineage_adjust:
        design = _lineage_design(model_meta, A.index)
        if design is not None:
            Ar = _residualize(Ar, design)
            Br = _residualize(Br, design)

    Au, Bu = _unit_columns(Ar), _unit_columns(Br)
    rho = Au.T @ Bu                              # r_xy: (driver x dep) CN-vs-effect
    rho = np.clip(rho, -0.9999999, 0.9999999)

    # ---- co-amplification structure, straight from the CN matrix ----------- #
    # Adep = copy number of each *dependency* gene (where it also exists in A),
    # ranked & residualized identically so the partial-correlation algebra holds.
    dep_in_A = np.array([g in A.columns for g in b_genes])
    Adep_raw = np.column_stack([
        Ar[:, list(A.columns).index(g)] if in_a else np.zeros(n)
        for g, in_a in zip(b_genes, dep_in_A)
    ])
    Adep_u = _unit_columns(Adep_raw)
    Adep_u[:, ~dep_in_A] = 0.0

    r_xz = Au.T @ Adep_u                         # corr(CN_driver, CN_dependency)
    r_yz = (Bu * Adep_u).sum(axis=0)            # corr(effect_dep, CN_dependency) per dep
    cn_corr = np.where(dep_in_A[None, :], r_xz, np.nan)

    # partial correlation r_xy.z = (r_xy - r_xz r_yz) / sqrt((1-r_xz^2)(1-r_yz^2))
    denom = np.sqrt(np.clip((1 - r_xz**2) * (1 - r_yz[None, :] ** 2), 1e-12, None))
    rho_partial = np.clip((rho - r_xz * r_yz[None, :]) / denom, -0.9999999, 0.9999999)

    def _two_sided_p(r, df):
        with np.errstate(divide="ignore", invalid="ignore"):
            t = r * np.sqrt(df / (1.0 - r**2))
        return 2.0 * stats.t.sf(np.abs(t), df=df)

    p = _two_sided_p(rho, n - 2)
    p_partial = _two_sided_p(rho_partial, n - 3)

    # OLS slope on the original (non-ranked) scale, for interpretability:
    # slope_xy = cov(x,y)/var(x), computed per driver across all dependencies.
    Ac = A.fillna(A.mean()).to_numpy(dtype=float)
    Bc = B.fillna(B.mean()).to_numpy(dtype=float)
    Acen = Ac - Ac.mean(0, keepdims=True)
    Bcen = Bc - Bc.mean(0, keepdims=True)
    cov = Acen.T @ Bcen / (n - 1)                # a x b
    var_a = (Acen**2).sum(0) / (n - 1)           # a
    var_a[var_a == 0] = np.nan
    slope = cov / var_a[:, None]

    # For trans pairs whose dependency CN is available, `control` swaps in the
    # partial correlation (and its p); cis pairs and unmeasurable pairs keep raw.
    a_arr = np.array(a_genes)
    is_cis = a_arr[:, None] == np.array(b_genes)[None, :]
    if params.coamp_handling == CoampHandling.control:
        use_partial = (~is_cis) & dep_in_A[None, :]
    else:
        use_partial = np.zeros_like(is_cis)
    eff = np.where(use_partial, rho_partial, rho)
    pv = np.where(use_partial, p_partial, p)

    ai, bi = np.meshgrid(np.arange(len(a_genes)), np.arange(len(b_genes)), indexing="ij")
    return pd.DataFrame(
        {
            "driver_gene": a_arr[ai.ravel()],
            "dependency_gene": np.array(b_genes)[bi.ravel()],
            "effect_metric": "spearman_rho",
            "effect_size": eff.ravel(),
            "slope": slope.ravel(),
            "p_value": pv.ravel(),
            "n": n,
            "cn_correlation": cn_corr.ravel(),
        }
    )


# --------------------------------------------------------------------------- #
# binary mode
# --------------------------------------------------------------------------- #
def _cn_cn_correlation(A: pd.DataFrame, dep_genes: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Spearman corr(CN_driver, CN_dependency) for every (driver, dep) pair.

    Returns (driver x dep) matrix and a dep_in_A mask; deps absent from A are 0
    in the matrix (masked to NaN by callers)."""
    cols = list(A.columns)
    n = len(A)
    Ar = _rankdata_columns(A.fillna(A.mean()).to_numpy(dtype=float))
    Au = _unit_columns(Ar)
    dep_in_A = np.array([g in A.columns for g in dep_genes])
    Adep = np.column_stack([
        Ar[:, cols.index(g)] if ina else np.zeros(n)
        for g, ina in zip(dep_genes, dep_in_A)
    ])
    Adep_u = _unit_columns(Adep)
    Adep_u[:, ~dep_in_A] = 0.0
    return Au.T @ Adep_u, dep_in_A


def _run_binary(A: pd.DataFrame, B: pd.DataFrame, params: ScreenParams) -> pd.DataFrame:
    b_genes = list(B.columns)
    Bv = B.to_numpy(dtype=float)
    rows = []

    cn_cc, dep_in_A = _cn_cn_correlation(A, b_genes)
    driver_idx = {g: i for i, g in enumerate(A.columns)}

    amp = params.direction in (Direction.amplification, Direction.both)
    for a_gene in A.columns:
        cn = A[a_gene].to_numpy(dtype=float)
        if amp:
            grp = cn >= params.amp_threshold
        else:  # deletion
            grp = cn <= params.del_threshold
        n1 = int(np.nansum(grp))
        n0 = int(np.nansum(~grp))
        if min(n1, n0) < params.min_group_size:
            continue

        block_in = Bv[grp]      # altered lines x b_genes
        block_out = Bv[~grp]    # other lines x b_genes
        # Mann-Whitney per dependency column; nan_policy omits missing gene effects.
        U, p = stats.mannwhitneyu(
            block_in, block_out, axis=0, alternative="two-sided", nan_policy="omit"
        )
        # Cliff's delta = 2*U/(n1*n0) - 1 with U for the altered group. scipy
        # orients U so this is already negative when the altered group has lower
        # (more negative) gene effect == stronger dependency, matching the
        # continuous mode's sign convention.
        cliffs = 2.0 * U / (n1 * n0) - 1.0

        cn_corr = np.where(dep_in_A, cn_cc[driver_idx[a_gene], :], np.nan)
        rows.append(
            pd.DataFrame(
                {
                    "driver_gene": a_gene,
                    "dependency_gene": b_genes,
                    "effect_metric": "cliffs_delta",
                    "effect_size": cliffs,
                    "slope": np.nan,
                    "p_value": np.asarray(p, dtype=float),
                    "n": n1 + n0,
                    "cn_correlation": cn_corr,
                }
            )
        )
    if not rows:
        return pd.DataFrame(
            columns=["driver_gene", "dependency_gene", "effect_metric",
                     "effect_size", "slope", "p_value", "n", "cn_correlation"]
        )
    return pd.concat(rows, ignore_index=True)


# --------------------------------------------------------------------------- #
# per-pair annotations
# --------------------------------------------------------------------------- #
def _annotate(
    res: pd.DataFrame,
    A: pd.DataFrame,
    B: pd.DataFrame,
    params: ScreenParams,
    mods: "amplicon.AmpliconModules | None" = None,
) -> pd.DataFrame:
    res = res.copy()
    same_gene = res["driver_gene"].values == res["dependency_gene"].values
    res["same_gene"] = same_gene

    # Relationship is cis when the driver IS the dependency, and also when the
    # dependency gene sits in the driver's own amplicon module (a co-amplified
    # passenger pointing at the amplicon's own dependency — mechanistically cis,
    # not a cross-locus discovery). The latter requires clustering to be on.
    if mods is not None:
        drv_mod = res["driver_gene"].map(mods.gene_to_module)
        dep_mod = res["dependency_gene"].map(mods.gene_to_module)
        in_amplicon = dep_mod.notna() & (drv_mod == dep_mod)
        cis = same_gene | in_amplicon.to_numpy()
    else:
        cis = same_gene
    res["relationship"] = np.where(cis, "cis", "trans")

    # amplification frequency per driver (fraction of lines >= amp threshold)
    amp_freq = ((A >= params.amp_threshold).mean()).to_dict()
    res["amp_frequency"] = res["driver_gene"].map(amp_freq).astype(float)

    # dependency-gene properties (selectivity, fraction dependent)
    dep_std = B.std().to_dict()
    frac_dep = (B < -0.5).mean().to_dict()
    res["dep_selectivity"] = res["dependency_gene"].map(dep_std).astype(float)
    res["frac_dependent"] = res["dependency_gene"].map(frac_dep).astype(float)
    return res


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
def run_screen(
    A: pd.DataFrame,
    B: pd.DataFrame,
    params: ScreenParams | None = None,
    model_meta: pd.DataFrame | None = None,
    common_essentials: set[str] | None = None,
) -> pd.DataFrame:
    """Run the full A x B screen and return a ranked, FDR-controlled result table.

    A, B are aligned on a shared line index by `filters.align`. The returned frame
    has one row per tested pair that passed the direction and FDR filters, sorted
    by ascending q-value then descending |effect|.
    """
    params = params or ScreenParams()

    A, B = filters.align(A, B)
    A = filters.prefilter_drivers(A, params)
    B = filters.prefilter_dependencies(B, params, common_essentials)
    if A.shape[1] == 0 or B.shape[1] == 0:
        return _empty_result()

    if params.mode == Mode.continuous:
        res = _run_continuous(A, B, params, model_meta)
    else:
        res = _run_binary(A, B, params)
    if res.empty:
        return _empty_result()

    # Cluster drivers into amplicon modules up front (when collapsing) so the
    # relationship filter below is module-aware: a passenger -> amplicon's-own
    # dependency is treated as cis, not trans.
    mods = (
        amplicon.cluster_drivers(A, params.amplicon_corr_threshold)
        if params.collapse_amplicons
        else None
    )
    res = res.dropna(subset=["p_value", "effect_size"])
    res = _annotate(res, A, B, params, mods)

    # Keep only pairs whose sign matches the hypothesised direction.
    # amplification/deletion both predict a NEGATIVE effect_size (CN change tracks
    # with stronger dependency); "both" keeps everything.
    if params.direction != Direction.both:
        res = res[res["effect_size"] < 0]
    if params.relationship == Relationship.cis:
        res = res[res["relationship"] == "cis"]
    elif params.relationship == Relationship.trans:
        res = res[res["relationship"] == "trans"]

    # Co-amplification: drop trans pairs whose driver CN tracks the dependency's
    # own CN (same amplicon). NaN cn_correlation (dependency not in A) is kept.
    if params.coamp_handling == CoampHandling.filter:
        coamp = (res["relationship"] == "trans") & (
            res["cn_correlation"].abs() >= params.coamp_threshold
        )
        res = res[~coamp]
    if res.empty:
        return _empty_result()

    # BH-FDR across all surviving tests.
    res = res.reset_index(drop=True)
    _, q, _, _ = multipletests(res["p_value"].values, method="fdr_bh")
    res["q_value"] = q

    res = res[res["q_value"] <= params.fdr_threshold]

    # Collapse co-amplified drivers into amplicon modules (one row per module x
    # dependency), reusing the modules clustered above.
    if mods is not None and not res.empty:
        res = amplicon.collapse(res, mods)

    res = res.sort_values(["q_value", "effect_size"], ascending=[True, True])
    res = res.head(params.max_results).reset_index(drop=True)
    return res


def _empty_result() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "driver_gene", "dependency_gene", "relationship", "n",
            "effect_metric", "effect_size", "slope", "p_value", "q_value",
            "amp_frequency", "dep_selectivity", "frac_dependent", "cn_correlation",
        ]
    )
