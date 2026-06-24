"""Pydantic models: analysis parameters, result rows, and agent I/O contracts.

These are the single source of truth for both the FastAPI layer and the agent
stubs. An agent (stub or live LLM) returns one of the *Report models below; the
frontend renders them identically either way.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Analysis parameters
# --------------------------------------------------------------------------- #
class Mode(str, Enum):
    continuous = "continuous"
    binary = "binary"


class Direction(str, Enum):
    """Which copy-number change we hypothesise induces a dependency."""
    amplification = "amplification"  # more copies -> stronger dependency
    deletion = "deletion"            # loss -> stronger dependency
    both = "both"


class Relationship(str, Enum):
    all = "all"
    cis = "cis"      # driver gene == dependency gene (oncogene addiction)
    trans = "trans"  # driver and dependency are different genes


class CoampHandling(str, Enum):
    """How to treat co-amplification between driver and dependency genes.

    A trans hit can be spurious when the driver is merely co-amplified with a
    cis-addicted dependency gene (e.g. FGF4 riding CCND1's 11q13 amplicon). We
    detect this directly from the CN matrix via corr(CN_driver, CN_dependency).
    """
    off = "off"          # ignore co-amplification entirely
    flag = "flag"        # annotate cn_correlation, change nothing else
    filter = "filter"    # drop trans pairs with |cn_correlation| >= threshold
    control = "control"  # partial out the dependency gene's own CN (continuous only)


class ScreenParams(BaseModel):
    """Knobs for one A x B screen. Defaults are tuned for DepMap log2(CN+1) data."""
    mode: Mode = Mode.continuous
    direction: Direction = Direction.amplification

    # Binary-mode thresholds, on the log2(relative_CN + 1) scale (diploid = 1.0).
    amp_threshold: float = Field(1.3, description="CN >= this counts as amplified")
    del_threshold: float = Field(0.7, description="CN <= this counts as deleted")
    min_group_size: int = Field(10, ge=2, description="min lines in the smaller group")

    # Prefilters
    min_cn_std: float = Field(0.10, description="drop driver genes flatter than this")
    exclude_common_essentials: bool = True
    lineage_adjust: bool = Field(
        False, description="partial out OncotreeLineage before correlating"
    )

    # Co-amplification handling (see CoampHandling)
    coamp_handling: CoampHandling = CoampHandling.flag
    coamp_threshold: float = Field(
        0.6, ge=0.0, le=1.0, description="|corr(CN_driver, CN_dep)| above which a trans pair is co-amplified"
    )

    # Driver-side amplicon clustering: collapse co-amplified drivers into one
    # module-level hit per dependency (de-duplicates redundant rows).
    collapse_amplicons: bool = False
    amplicon_corr_threshold: float = Field(
        0.7, ge=0.0, le=1.0, description="corr(CN) above which two drivers share an amplicon module"
    )

    # Significance / output
    fdr_threshold: float = Field(0.10, ge=0.0, le=1.0)
    relationship: Relationship = Relationship.all
    max_results: int = Field(500, ge=1, le=2000)


# --------------------------------------------------------------------------- #
# Result rows
# --------------------------------------------------------------------------- #
class CandidatePair(BaseModel):
    """One driver(CN) -> dependency(CRISPR) relationship that passed testing."""
    driver_gene: str
    dependency_gene: str
    relationship: Literal["cis", "trans"]

    n: int
    effect_metric: str            # "spearman_rho" | "cliffs_delta"
    effect_size: float            # signed; negative => CN-up associates with dependency-up
    slope: Optional[float] = None  # OLS slope (continuous mode)
    p_value: float
    q_value: float                # BH-FDR

    amp_frequency: float          # fraction of lines amplified for the driver
    dep_selectivity: float        # std of dependency gene effect across lines
    frac_dependent: float         # fraction of lines with gene effect < -0.5
    cn_correlation: Optional[float] = None  # corr(CN_driver, CN_dependency); high => co-amplicon

    # Amplicon module (when collapse_amplicons is on)
    module_label: Optional[str] = None      # e.g. "ZNF217 +5"
    module_size: Optional[int] = None       # co-amplified drivers in the module
    module_members: Optional[str] = None    # members that independently hit this dependency
    n_module_drivers: Optional[int] = None

    # Filled in by scoring.py
    component_scores: dict[str, float] = Field(default_factory=dict)
    composite_score: Optional[float] = None


# --------------------------------------------------------------------------- #
# Agent I/O contracts (stubbed now, LLM-backed later — same shape either way)
# --------------------------------------------------------------------------- #
class Citation(BaseModel):
    title: str
    url: Optional[str] = None
    year: Optional[int] = None
    snippet: Optional[str] = None


class LiteratureReport(BaseModel):
    """Literature-research agent: known mechanistic support for the pair."""
    support_score: float = Field(..., ge=0, le=1, description="0=no link, 1=well established")
    summary: str
    citations: list[Citation] = Field(default_factory=list)


class PrecedentReport(BaseModel):
    """Precedent agent: has this target/relationship been pursued?"""
    novelty_score: float = Field(..., ge=0, le=1, description="1=white space, 0=crowded")
    status: Literal["novel", "emerging", "crowded"]
    summary: str
    programs: list[str] = Field(default_factory=list)


class TractabilityBucket(BaseModel):
    label: str
    modality: Literal["SM", "AB", "PR", "OC"]
    value: bool


class TargetabilityReport(BaseModel):
    """Open Targets tractability for the dependency gene."""
    ensembl_id: Optional[str] = None
    targetability_score: float = Field(..., ge=0, le=1)
    top_modality: Optional[str] = None
    buckets: list[TractabilityBucket] = Field(default_factory=list)


class MolecularReport(BaseModel):
    """Molecular-design agent: feasibility of drugging the dependency gene."""
    feasibility_score: float = Field(..., ge=0, le=1)
    summary: str
    proposed_chemotypes: list[str] = Field(default_factory=list)


class CandidateDossier(BaseModel):
    """A candidate enriched with all agent reports — the per-row expandable panel."""
    pair: CandidatePair
    literature: Optional[LiteratureReport] = None
    precedent: Optional[PrecedentReport] = None
    targetability: Optional[TargetabilityReport] = None
    molecular: Optional[MolecularReport] = None
