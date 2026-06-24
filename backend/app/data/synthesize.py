"""Synthetic DepMap-shaped data with known ground truth.

Used to validate the engine: we plant relationships and confounds we can assert
on. Values mimic real scales — A is log2(relative_CN + 1) (diploid = 1.0), B is
Chronos gene effect (0 = no effect, negative = dependency). Gene columns carry a
fake Entrez suffix so the full name-normalization path is exercised.

Planted truth
-------------
cis    : ERBB2 amplified -> ERBB2 dependency (oncogene addiction)
cis    : MYC   amplified -> MYC   dependency
trans  : CCNE1 amplified -> CDK2  dependency (a different gene becomes essential)
confound: lineage 'Breast' lines tend to amplify FOO_CN *and* depend on BAR_DEP,
          with no causal CN->dependency link — naive corr sees it, lineage
          adjustment should remove it.
common-essential: POLR2A, RPL3 are essential in *every* line (filtered out).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class SyntheticData:
    A: pd.DataFrame                  # copy number, log2(CN+1)
    B: pd.DataFrame                  # CRISPR gene effect (Chronos)
    model_meta: pd.DataFrame         # OncotreeLineage per line
    common_essentials: set[str]      # bare symbols
    true_cis: list[tuple[str, str]]      # (driver, dependency)
    true_trans: list[tuple[str, str]]
    confound_pairs: list[tuple[str, str]] = field(default_factory=list)
    coamp_passengers: list[tuple[str, str]] = field(default_factory=list)


def _entrez(symbol: str, i: int) -> str:
    return f"{symbol} ({1000 + i})"


def generate(n_lines: int = 400, n_noise: int = 250, seed: int = 7) -> SyntheticData:
    rng = np.random.default_rng(seed)
    lines = [f"ACH-{i:06d}" for i in range(n_lines)]
    lineages = rng.choice(
        ["Breast", "Lung", "Colon", "Skin", "Ovary", "Blood"], size=n_lines
    )
    model_meta = pd.DataFrame({"OncotreeLineage": lineages}, index=lines)

    A_cols: dict[str, np.ndarray] = {}
    B_cols: dict[str, np.ndarray] = {}

    # baseline copy number ~ diploid, gene effect ~ no effect
    def cn_baseline():
        return rng.normal(1.0, 0.12, n_lines)

    def ge_baseline():
        return rng.normal(0.0, 0.12, n_lines)

    # ---- planted CIS relationships --------------------------------------- #
    true_cis = []
    cis_cn: dict[str, np.ndarray] = {}
    for idx, gene in enumerate(["ERBB2", "MYC"]):
        amplified = rng.random(n_lines) < 0.18
        cn = cn_baseline()
        cn[amplified] = rng.normal(2.1, 0.30, amplified.sum())
        ge = ge_baseline()
        ge[amplified] = rng.normal(-1.1, 0.20, amplified.sum())  # addiction
        A_cols[_entrez(gene, idx)] = cn
        B_cols[_entrez(gene, idx)] = ge
        cis_cn[gene] = cn
        true_cis.append((gene, gene))

    # ---- co-amplicon PASSENGER of ERBB2 ---------------------------------- #
    # PASSERB shares ERBB2's copy-number profile (same amplicon) but its own
    # knockout does nothing. PASSERB -> ERBB2(effect) is therefore a SPURIOUS
    # trans hit, explained entirely by ERBB2's own CN. cn_correlation should be
    # high; control/filter should remove it while the real ERBB2 cis and the
    # real CCNE1->CDK2 trans survive.
    A_cols[_entrez("PASSERB", 60)] = cis_cn["ERBB2"] + rng.normal(0, 0.05, n_lines)
    B_cols[_entrez("PASSERB", 60)] = ge_baseline()
    coamp_passengers = [("PASSERB", "ERBB2")]

    # ---- planted TRANS relationship: CCNE1 amp -> CDK2 dependency -------- #
    amplified = rng.random(n_lines) < 0.15
    cn = cn_baseline()
    cn[amplified] = rng.normal(2.0, 0.30, amplified.sum())
    A_cols[_entrez("CCNE1", 50)] = cn
    A_cols[_entrez("CDK2", 51)] = cn_baseline()      # CDK2 CN is unrelated/flat-ish
    cdk2_ge = ge_baseline()
    cdk2_ge[amplified] = rng.normal(-0.9, 0.20, amplified.sum())
    B_cols[_entrez("CDK2", 51)] = cdk2_ge
    B_cols[_entrez("CCNE1", 50)] = ge_baseline()     # CCNE1 itself not essential
    true_trans = [("CCNE1", "CDK2")]

    # ---- lineage CONFOUND (no causal CN->dep link) ----------------------- #
    is_breast = lineages == "Breast"
    foo_cn = cn_baseline()
    foo_cn[is_breast] = rng.normal(1.9, 0.30, is_breast.sum())   # Breast amplifies FOO
    bar_ge = ge_baseline()
    bar_ge[is_breast] = rng.normal(-0.9, 0.20, is_breast.sum())  # Breast depends on BAR
    A_cols[_entrez("FOO_CN", 80)] = foo_cn
    B_cols[_entrez("BAR_DEP", 81)] = bar_ge
    confound_pairs = [("FOO_CN", "BAR_DEP")]

    # ---- common essentials (essential everywhere) ------------------------ #
    common = []
    for idx, gene in enumerate(["POLR2A", "RPL3"]):
        A_cols[_entrez(gene, 90 + idx)] = cn_baseline()
        B_cols[_entrez(gene, 90 + idx)] = rng.normal(-1.0, 0.10, n_lines)
        common.append(gene)

    # ---- noise genes ----------------------------------------------------- #
    for i in range(n_noise):
        # some noise drivers carry a random amplification so prefilter sees variance
        cn = cn_baseline()
        if rng.random() < 0.4:
            amp = rng.random(n_lines) < rng.uniform(0.05, 0.25)
            cn[amp] = rng.normal(1.9, 0.3, amp.sum())
        A_cols[_entrez(f"NOISEA{i}", 200 + i)] = cn
        B_cols[_entrez(f"NOISEB{i}", 600 + i)] = ge_baseline()

    A = pd.DataFrame(A_cols, index=lines)
    B = pd.DataFrame(B_cols, index=lines)
    return SyntheticData(
        A=A,
        B=B,
        model_meta=model_meta,
        common_essentials=set(common),
        true_cis=true_cis,
        true_trans=true_trans,
        confound_pairs=confound_pairs,
        coamp_passengers=coamp_passengers,
    )
