"""Trim raw DepMap 23Q4 matrices into a compact, bundleable demo subset.

Input  (in scripts/.depmap_cache/, downloaded from Figshare — see fetch_depmap.sh):
    CRISPRGeneEffect.csv               ~382 MB   lines x genes (Chronos)
    OmicsCNGene.csv                    ~763 MB   lines x genes (log2(CN+1))
    Model.csv                          model metadata
    AchillesCommonEssentialControls.csv
    CRISPRInferredCommonEssentials.csv

Output (app/data/depmap_subset/):
    copy_number.parquet   gene_effect.parquet   model.parquet   common_essentials.txt

The panel keeps (a) a curated set of recurrently amplified oncogenes in BOTH
matrices — so cis oncogene-addiction signals (ERBB2, MYC, ...) are present as a
built-in positive control — plus (b) the most variable remaining copy-number
drivers and the most variable (selective) dependencies.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

CACHE = Path(__file__).parent / ".depmap_cache"
OUT = Path(__file__).parents[1] / "app" / "data" / "depmap_subset"
_PAREN = re.compile(r"\s*\(\d+\)\s*$")

# Recurrently amplified oncogenes — the cis positive-control set.
ONCOGENES = [
    "ERBB2", "MYC", "MYCN", "MYCL", "EGFR", "KRAS", "MET", "CCND1", "CCNE1",
    "CDK4", "CDK6", "MDM2", "MDM4", "FGFR1", "FGFR2", "AR", "BCL2L1", "MCL1",
    "TERT", "SOX2", "KIT", "PDGFRA", "AKT1", "AKT2", "PIK3CA", "NKX2-1",
    "YAP1", "CCND2", "CDK2", "AURKA", "BRAF", "IGF1R", "ZNF217", "GATA6",
]

N_DRIVERS = 500       # extra high-variance CN genes beyond the oncogenes
N_DEPENDENCIES = 500  # extra high-variance dependencies beyond the oncogenes


def _bare(name: str) -> str:
    return _PAREN.sub("", str(name)).strip()


def _pick(df: pd.DataFrame, must_have: set[str], n_extra: int) -> list[str]:
    """Keep all columns whose bare symbol is in must_have, plus the top-n_extra
    most variable remaining columns."""
    bare = {c: _bare(c) for c in df.columns}
    forced = [c for c in df.columns if bare[c] in must_have]
    rest = [c for c in df.columns if bare[c] not in must_have]
    var = df[rest].var().sort_values(ascending=False)
    extra = list(var.head(n_extra).index)
    return forced + extra


def main() -> int:
    if not (CACHE / "CRISPRGeneEffect.csv").exists():
        print(f"Raw files not found in {CACHE}. Run fetch_depmap.sh first.", file=sys.stderr)
        return 1

    print("reading CRISPR gene effect ...", flush=True)
    B = pd.read_csv(CACHE / "CRISPRGeneEffect.csv", index_col=0)
    print(f"  {B.shape[0]} lines x {B.shape[1]} genes", flush=True)

    print("reading copy number ...", flush=True)
    A = pd.read_csv(CACHE / "OmicsCNGene.csv", index_col=0)
    print(f"  {A.shape[0]} lines x {A.shape[1]} genes", flush=True)

    onco = set(ONCOGENES)
    a_cols = _pick(A, onco, N_DRIVERS)
    b_cols = _pick(B, onco, N_DEPENDENCIES)

    # Coverage: ensure the CN panel includes every dependency gene that has CN
    # data, so corr(CN_driver, CN_dependency) is computable for co-amplification
    # handling (otherwise the dependency's own CN is unknown -> cn_correlation NaN
    # and co-amplified trans hits slip through the filter untested).
    b_bare = {_bare(c) for c in b_cols}
    a_have = {_bare(c) for c in a_cols}
    coverage = [c for c in A.columns if _bare(c) in b_bare and _bare(c) not in a_have]
    a_cols = a_cols + coverage
    print(f"added {len(coverage)} CN columns to cover dependency genes", flush=True)

    A = A[a_cols].astype("float32")
    B = B[b_cols].astype("float32")

    shared = A.index.intersection(B.index)
    A, B = A.loc[shared], B.loc[shared]
    print(f"shared lines: {len(shared)}; drivers: {A.shape[1]}; dependencies: {B.shape[1]}",
          flush=True)

    # model metadata, restricted to shared lines
    model = pd.read_csv(CACHE / "Model.csv", index_col=0)
    keep_meta = [c for c in ["OncotreeLineage", "OncotreePrimaryDisease",
                             "OncotreeSubtype", "PrimaryOrMetastasis"] if c in model.columns]
    model = model.loc[model.index.intersection(shared), keep_meta]

    # common essentials: union of the two reference lists, as bare symbols
    common: set[str] = set()
    for fn in ["AchillesCommonEssentialControls.csv", "CRISPRInferredCommonEssentials.csv"]:
        p = CACHE / fn
        if p.exists():
            col = pd.read_csv(p)
            common |= {_bare(x) for x in col.iloc[:, 0].dropna()}
    print(f"common essentials: {len(common)}", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    A.to_parquet(OUT / "copy_number.parquet")
    B.to_parquet(OUT / "gene_effect.parquet")
    model.to_parquet(OUT / "model.parquet")
    (OUT / "common_essentials.txt").write_text("\n".join(sorted(common)))

    sizes = {p.name: f"{p.stat().st_size/1e6:.1f} MB" for p in OUT.glob('*')}
    print("wrote subset:", sizes, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
