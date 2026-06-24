"""Validate the engine against planted ground truth.

We assert the engine (a) recovers planted cis and trans relationships, (b) keeps
common essentials out when asked, and (c) lets lineage adjustment dissolve a
purely lineage-driven confound.
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.analysis import engine, filters, scoring
from app.data import synthesize
from app.schemas import CoampHandling, Direction, Mode, Relationship, ScreenParams


@pytest.fixture(scope="module")
def syn():
    return synthesize.generate()


def _pairs(res: pd.DataFrame) -> set[tuple[str, str]]:
    return set(zip(res["driver_gene"], res["dependency_gene"]))


def test_continuous_recovers_cis_and_trans(syn):
    params = ScreenParams(mode=Mode.continuous, direction=Direction.amplification)
    res = engine.run_screen(syn.A, syn.B, params, syn.model_meta, syn.common_essentials)
    found = _pairs(res)
    for pair in syn.true_cis + syn.true_trans:
        assert pair in found, f"missed planted pair {pair}"
    # planted hits should be near the top by effect size
    res = res.sort_values("effect_size")  # most negative first
    top = _pairs(res.head(10))
    assert ("ERBB2", "ERBB2") in top
    assert ("CCNE1", "CDK2") in top


def test_binary_recovers_cis(syn):
    params = ScreenParams(mode=Mode.binary, direction=Direction.amplification,
                          amp_threshold=1.5, min_group_size=8)
    res = engine.run_screen(syn.A, syn.B, params, syn.model_meta, syn.common_essentials)
    found = _pairs(res)
    assert ("ERBB2", "ERBB2") in found
    assert ("CCNE1", "CDK2") in found


def test_common_essentials_excluded(syn):
    params = ScreenParams(exclude_common_essentials=True)
    res = engine.run_screen(syn.A, syn.B, params, syn.model_meta, syn.common_essentials)
    assert "POLR2A" not in set(res["dependency_gene"])
    assert "RPL3" not in set(res["dependency_gene"])


def test_cis_label_correct(syn):
    res = engine.run_screen(syn.A, syn.B, ScreenParams(), syn.model_meta, syn.common_essentials)
    cis_rows = res[res["relationship"] == "cis"]
    assert (cis_rows["driver_gene"] == cis_rows["dependency_gene"]).all()


def test_lineage_adjustment_dissolves_confound(syn):
    """FOO_CN->BAR_DEP is purely lineage-driven; adjustment should weaken it."""
    base = engine.run_screen(
        syn.A, syn.B, ScreenParams(lineage_adjust=False), syn.model_meta, syn.common_essentials
    )
    adj = engine.run_screen(
        syn.A, syn.B, ScreenParams(lineage_adjust=True), syn.model_meta, syn.common_essentials
    )
    confound = syn.confound_pairs[0]
    # Confound is detected without adjustment...
    assert confound in _pairs(base)
    # ...and removed (or strongly weakened) with lineage adjustment, while the
    # genuine causal CIS hit survives both.
    assert confound not in _pairs(adj)
    assert ("ERBB2", "ERBB2") in _pairs(adj)


def test_coamp_flag_annotates_passenger(syn):
    """A co-amplicon passenger (PASSERB) is surfaced and flagged with high CN corr."""
    params = ScreenParams(coamp_handling=CoampHandling.flag)
    res = engine.run_screen(syn.A, syn.B, params, syn.model_meta, syn.common_essentials)
    drv, dep = syn.coamp_passengers[0]
    row = res[(res.driver_gene == drv) & (res.dependency_gene == dep)]
    assert not row.empty, "passenger should appear under flag mode"
    assert row["cn_correlation"].iloc[0] > 0.8
    # genuine ERBB2 cis CN-correlation with itself is also high but it's labeled cis
    assert (res[res.relationship == "cis"]["cn_correlation"].dropna() > 0.95).all()


def test_coamp_filter_removes_passenger_keeps_real(syn):
    params = ScreenParams(coamp_handling=CoampHandling.filter, coamp_threshold=0.6)
    res = engine.run_screen(syn.A, syn.B, params, syn.model_meta, syn.common_essentials)
    pairs = _pairs(res)
    assert syn.coamp_passengers[0] not in pairs        # passenger filtered out
    assert ("CCNE1", "CDK2") in pairs                  # real trans survives
    assert ("ERBB2", "ERBB2") in pairs                 # real cis survives


def test_coamp_control_demotes_passenger(syn):
    """Partialling out the dependency's own CN collapses the passenger signal."""
    params = ScreenParams(coamp_handling=CoampHandling.control)
    res = engine.run_screen(syn.A, syn.B, params, syn.model_meta, syn.common_essentials)
    pairs = _pairs(res)
    assert syn.coamp_passengers[0] not in pairs        # partial corr ~ 0 -> fails FDR
    assert ("CCNE1", "CDK2") in pairs                  # CN-independent trans survives
    assert ("ERBB2", "ERBB2") in pairs                 # cis kept raw


def test_amplicon_collapse_dedupes_coamplified_drivers(syn):
    """PASSERB and ERBB2 are co-amplified -> one module row for dependency ERBB2."""
    params = ScreenParams(collapse_amplicons=True, amplicon_corr_threshold=0.7)
    res = engine.run_screen(syn.A, syn.B, params, syn.model_meta, syn.common_essentials)

    erbb2 = res[res.dependency_gene == "ERBB2"]
    multi = erbb2[erbb2.module_size > 1]
    assert len(multi) == 1, "the ERBB2 amplicon should appear as a single module row"
    row = multi.iloc[0]
    assert row.module_size >= 2
    assert "PASSERB" in row.module_members and "ERBB2" in row.module_members
    # the redundant passenger row is gone; genuine CN-independent trans survives
    assert ("PASSERB", "ERBB2") not in _pairs(res) or row.driver_gene == "PASSERB"
    assert ("CCNE1", "CDK2") in _pairs(res)


def test_amplicon_collapse_preserves_independent_hits(syn):
    """Collapsing must not merge CN-independent drivers."""
    params = ScreenParams(collapse_amplicons=True)
    res = engine.run_screen(syn.A, syn.B, params, syn.model_meta, syn.common_essentials)
    # CCNE1 (its own amplicon) and the cis genes stay as distinct module rows
    assert ("CCNE1", "CDK2") in _pairs(res)
    assert ("MYC", "MYC") in _pairs(res)
    assert res["module_size"].min() >= 1


def test_in_amplicon_passenger_labeled_cis_when_collapsing(syn):
    """A passenger pointing at its amplicon's own dependency (PASSERB->ERBB2,
    where ERBB2 is in PASSERB's module) is cis, not a cross-locus trans hit."""
    # Excluded from the trans view entirely.
    trans = engine.run_screen(
        syn.A, syn.B,
        ScreenParams(relationship=Relationship.trans, collapse_amplicons=True),
        syn.model_meta, syn.common_essentials,
    )
    assert syn.coamp_passengers[0] not in _pairs(trans)

    # Under "all", the ERBB2 amplicon collapses to a single cis row led by the
    # true same-gene pair ERBB2->ERBB2.
    allr = engine.run_screen(
        syn.A, syn.B,
        ScreenParams(relationship=Relationship.all, collapse_amplicons=True),
        syn.model_meta, syn.common_essentials,
    )
    erbb2_mod = allr[(allr.dependency_gene == "ERBB2") & (allr.module_size > 1)]
    assert len(erbb2_mod) == 1
    assert erbb2_mod.iloc[0]["relationship"] == "cis"
    assert erbb2_mod.iloc[0]["driver_gene"] == "ERBB2"


def test_relationship_stays_gene_level_without_collapse(syn):
    """With collapsing off, relationship is the plain gene-level cis/trans."""
    res = engine.run_screen(
        syn.A, syn.B,
        ScreenParams(relationship=Relationship.trans, collapse_amplicons=False),
        syn.model_meta, syn.common_essentials,
    )
    # the passenger is a distinct gene from ERBB2 -> still trans here
    assert syn.coamp_passengers[0] in _pairs(res)


def test_one_sided_p_is_half_two_sided(syn):
    """Directional (one-sided) p equals exactly half the two-sided p for a hit in
    the hypothesised direction (fix #2)."""
    A, B = filters.align(syn.A, syn.B)
    one = engine._run_continuous(A, B, ScreenParams(direction=Direction.amplification), None)
    two = engine._run_continuous(A, B, ScreenParams(direction=Direction.both), None)
    sel = lambda d: d[(d.driver_gene == "ERBB2") & (d.dependency_gene == "ERBB2")].iloc[0]
    p1, p2 = sel(one).p_value, sel(two).p_value
    assert sel(one).effect_size < 0  # in the hypothesised (amplification) direction
    assert p1 == pytest.approx(p2 / 2, rel=1e-6)


def test_deletion_direction_recovers_loss_dependency(syn):
    """A deletion-induced dependency surfaces only under direction=deletion, with
    the oriented (negative) effect-size convention (fix #2 / sign fix)."""
    res = engine.run_screen(
        syn.A, syn.B, ScreenParams(mode=Mode.continuous, direction=Direction.deletion),
        syn.model_meta, syn.common_essentials,
    )
    assert syn.true_deletion[0] in _pairs(res)
    row = res[(res.driver_gene == "DELDR") & (res.dependency_gene == "DELDEP")].iloc[0]
    assert row.effect_size < 0  # oriented: negative = loss induces dependency


def test_amplification_excludes_deletion_signal(syn):
    """The deletion signal must NOT appear in an amplification-direction screen."""
    res = engine.run_screen(
        syn.A, syn.B, ScreenParams(mode=Mode.continuous, direction=Direction.amplification),
        syn.model_meta, syn.common_essentials,
    )
    assert syn.true_deletion[0] not in _pairs(res)


def test_collapse_before_fdr_recovers_planted_hits(syn):
    """With amplicon collapse on (FDR over distinct modules), planted hits still
    pass (fix #1)."""
    res = engine.run_screen(
        syn.A, syn.B, ScreenParams(collapse_amplicons=True),
        syn.model_meta, syn.common_essentials,
    )
    found = _pairs(res)
    assert ("CCNE1", "CDK2") in found
    assert (res["q_value"] <= 0.1).all()


def test_scoring_runs_and_ranks(syn):
    res = engine.run_screen(syn.A, syn.B, ScreenParams(), syn.model_meta, syn.common_essentials)
    scored = scoring.composite_score(res)
    assert "composite_score" in scored.columns
    assert scored["composite_score"].between(0, 1).all()
    assert scored["composite_score"].is_monotonic_decreasing
    # component dict is populated for the API layer
    assert set(scored.iloc[0]["component_scores"]) >= {"effect", "confidence", "targetability"}
