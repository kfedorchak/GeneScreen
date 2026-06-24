"""Load datasets for a screen: the bundled DepMap demo subset, or user CSVs.

Bundled subset lives in app/data/depmap_subset/ as compact parquet:
  copy_number.parquet      lines x genes, log2(relative_CN + 1)
  gene_effect.parquet      lines x genes, Chronos gene effect
  model.parquet            lines x metadata (OncotreeLineage, ...)
  common_essentials.txt    one gene per line
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

SUBSET_DIR = Path(__file__).parent / "depmap_subset"


@dataclass
class Dataset:
    A: pd.DataFrame                     # copy number
    B: pd.DataFrame                     # gene effect
    model_meta: pd.DataFrame | None
    common_essentials: set[str]
    source: str


def _read_common_essentials(path: Path) -> set[str]:
    if not path.exists():
        return set()
    text = path.read_text().strip().splitlines()
    return {line.strip() for line in text if line.strip()}


def load_demo_subset(subset_dir: Path | str = SUBSET_DIR) -> Dataset:
    """Load the bundled real-DepMap demo subset."""
    d = Path(subset_dir)
    A = pd.read_parquet(d / "copy_number.parquet")
    B = pd.read_parquet(d / "gene_effect.parquet")
    model_path = d / "model.parquet"
    model_meta = pd.read_parquet(model_path) if model_path.exists() else None
    common = _read_common_essentials(d / "common_essentials.txt")
    return Dataset(A=A, B=B, model_meta=model_meta, common_essentials=common,
                   source="DepMap 23Q4 demo subset")


def load_csv_pair(
    cn_csv: str | Path,
    effect_csv: str | Path,
    model_csv: str | Path | None = None,
    common_essentials_path: str | Path | None = None,
) -> Dataset:
    """Load a user-supplied A/B pair. First column is the sample/line ID index."""
    A = pd.read_csv(cn_csv, index_col=0)
    B = pd.read_csv(effect_csv, index_col=0)
    model_meta = pd.read_csv(model_csv, index_col=0) if model_csv else None
    common = (
        _read_common_essentials(Path(common_essentials_path))
        if common_essentials_path
        else set()
    )
    return Dataset(A=A, B=B, model_meta=model_meta, common_essentials=common,
                   source="user upload")
