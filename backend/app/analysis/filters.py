"""Alignment and prefilters applied before the screen.

Two prefilters matter scientifically:
  * driver prefilter — drop copy-number genes that barely vary across lines;
    they carry no signal and only inflate the multiple-testing burden.
  * dependency prefilter — drop common-essential genes (essential in *every*
    line regardless of CN). These would otherwise dominate the hit list with
    ribosome/proteasome/spliceosome genes that are not selective, druggable
    opportunities. The interesting signal is *selective* dependency.
"""
from __future__ import annotations

import re

import pandas as pd

from ..schemas import ScreenParams


_PAREN = re.compile(r"\s*\(\d+\)\s*$")


def strip_entrez(name: str) -> str:
    """'ERBB2 (2064)' -> 'ERBB2'. Leaves already-clean symbols untouched."""
    return _PAREN.sub("", str(name)).strip()


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with gene columns reduced to bare HGNC symbols."""
    df = df.copy()
    df.columns = [strip_entrez(c) for c in df.columns]
    # collapse accidental duplicate symbols by keeping the first
    df = df.loc[:, ~pd.Index(df.columns).duplicated()]
    return df


def align(A: pd.DataFrame, B: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Normalize gene names and align A, B on their shared line index."""
    A, B = normalize_columns(A), normalize_columns(B)
    shared = A.index.intersection(B.index)
    return A.loc[shared], B.loc[shared]


def prefilter_drivers(A: pd.DataFrame, params: ScreenParams) -> pd.DataFrame:
    """Keep copy-number genes with enough variance to carry signal."""
    keep = A.std(axis=0) >= params.min_cn_std
    return A.loc[:, keep[keep].index]


def prefilter_dependencies(
    B: pd.DataFrame, params: ScreenParams, common_essentials: set[str] | None
) -> pd.DataFrame:
    """Optionally drop common-essential genes; always drop flat (never-varying) ones."""
    B = B.loc[:, B.std(axis=0) > 0]
    if params.exclude_common_essentials and common_essentials:
        ce = {strip_entrez(g) for g in common_essentials}
        keep = [g for g in B.columns if g not in ce]
        B = B.loc[:, keep]
    return B
