# GeneScreen

Discover **copy-number-associated dependencies** in cancer: genes that become
essential for tumor survival (CRISPR knockout) when a — potentially different —
gene is amplified or deleted. Built on DepMap-style data, with a tunable
statistical engine, a composite target-ranking score, and a (forthcoming)
agent-augmented dossier per candidate.

> Status: **Phase 1 complete** — analysis engine + scoring, validated on real
> DepMap 23Q4 data. API, frontend, and agent panels are next.

## The question

- **Dataset A** — copy number, one row per cell line, columns = genes,
  `log2(relative_CN + 1)` (diploid ≈ 1.0).
- **Dataset B** — CRISPR gene effect (Chronos), same lines; 0 = no effect,
  negative = knockout shrank the tumor (a dependency).

> Find genes in B that become essential given more copies of a (possibly
> different) gene in A — ranked by effect size and druggability.

## Approach

For every driver(A) × dependency(B) pair:

- **Continuous mode** — Spearman correlation of CN vs gene effect across lines,
  vectorised as one matrix product; optional **lineage adjustment** (partial out
  `OncotreeLineage`) to avoid rediscovering tissue-of-origin confounds.
- **Binary mode** — split lines amplified/not by a CN threshold, Mann-Whitney U
  on each dependency, effect size = Cliff's delta.

A *negative* effect size means more copies track with stronger dependency.
Multiple testing is controlled with Benjamini-Hochberg across all tested pairs.
Common-essential (pan-lethal) genes are filtered so hits are *selective*
dependencies, not ribosome/proteasome genes.

### Composite ranking (`analysis/scoring.py`)

Transparent, tunable weighted sum of 0–1 components: effect size, statistical
confidence, selectivity, amplification prevalence, plus targetability and
agent-derived components (bio-support, novelty) that default to neutral until
the agents are wired in.

## Validation

On the real DepMap 23Q4 subset the engine recovers textbook **oncogene
addiction** (cis) hits as a built-in positive control: CCND1, ERBB2, YAP1,
IGF1R, MDM2, AKT1, CDK6, MCL1, CCNE1, BRAF, EGFR, PIK3CA. Synthetic ground-truth
tests (`tests/test_engine_synthetic.py`) assert recovery of planted cis/trans
signals, common-essential exclusion, and lineage-confound removal.

### Co-amplification handling

A naive trans hit is often a **co-amplicon passenger**: FGF3/FGF4/FGF19/MYEOV
sit on CCND1's 11q13 amplicon, so their copy number tracks CCND1's and they
inherit CCND1's cis dependency. We detect this **directly from the CN matrix**
(no external coordinates) via `corr(CN_driver, CN_dependency)`, which *is* the
confounder — a strictly better signal than a cytoband proxy. `coamp_handling`:

* `flag` (default) — annotate `cn_correlation`; hide nothing.
* `filter` — drop trans pairs with `|cn_correlation| >= coamp_threshold`.
* `control` — partial out the dependency gene's **own** copy number; passenger
  signal collapses, CN-independent trans survives.

On real data this removes the 34 CCND1-amplicon passengers and surfaces genuine
cross-locus candidates (`cn_correlation ≈ 0.02`). `build_subset.py` makes the CN
panel cover all dependency genes so co-amplification is always assessable (99%).

### Driver-side amplicon clustering

The sibling confounder: many co-amplified *drivers* (a 20q amplicon) all point at
one dependency, producing dozens of statistically indistinguishable rows. With
`collapse_amplicons`, drivers whose CN profiles correlate above
`amplicon_corr_threshold` are grouped into **modules** (connected components of
the CN-correlation graph; labeled by their lead oncogene), and each
(module, dependency) collapses to one representative row listing the members
(`analysis/amplicon.py`). On real data this cuts 4,478 trans rows to 497 — e.g.
`ZNF217 +11 → UFM1` (20q13), `CCND1 +53 → ERBB2` (11q13) — each a single row
instead of a dozen.

When clustering is on, **relationship is module-aware**: a passenger pointing at
its own amplicon's dependency (e.g. a co-amplified neighbor → CCND1, where CCND1
is in that amplicon) is labeled `cis`, not a spurious cross-locus `trans`, and
the true same-gene pair (CCND1 → CCND1) is preferred as the row's representative.

## Layout

```
backend/
  app/
    schemas.py            Pydantic: params, result rows, agent I/O contracts
    analysis/
      engine.py           the A×B screen (continuous + binary, BH-FDR)
      filters.py          alignment, variance + common-essential prefilters
      scoring.py          composite ranking
    data/
      loader.py           bundled demo subset / CSV upload
      synthesize.py       synthetic ground-truth generator (for tests)
      depmap_subset/      compact real DepMap 23Q4 subset (parquet)
  scripts/
    fetch_depmap.sh       download raw DepMap matrices (Figshare, ungated)
    build_subset.py       trim raw matrices -> bundled subset
  tests/
```

## Web app

FastAPI serves the analysis engine under `/api/*` and the built React app at `/`:

```
GET  /api/dataset      shape + lineages of the loaded subset
POST /api/screen       ScreenParams -> ranked candidates (+ component scores)
GET  /api/pair_detail  per-line CN vs gene-effect scatter for the dossier
```

The UI is setup panel → ranked table → candidate dossier. Composite weights
re-rank **live** in the browser (component scores travel with each row). The
dossier shows the CN-vs-dependency scatter (colored by lineage) and the agent
dossier.

### Agents (`app/agents/`)

Each agent returns one of the `*Report` Pydantic contracts in `schemas.py`, so a
stub and a future LLM-backed implementation are interchangeable:

- **Targetability** — **LIVE** Open Targets GraphQL `tractability`; buckets →
  a 0-1 score (best passed bucket across SM/AB/PR modalities). Cached to
  `data/targetability_cache.json` (pre-warmed for all 534 dependency genes via
  `scripts/prewarm_targetability.py`) so the demo is instant and we don't loop
  the API. Live fallback for uncached genes (e.g. uploads).
- **Literature / Precedent / Molecular** — deterministic, clearly-labeled
  *simulated* stubs feeding the `bio_support`, `novelty`, and design-feasibility
  signals. Same interface a live model would implement.

`POST /api/screen` enriches the top `ENRICH_N` candidates' `targetability` /
`bio_support` / `novelty` components into the composite at screen time;
`GET /api/dossier` returns the full four-agent report for one candidate. The
Edison agent map (data-analysis / literature / precedent / molecular-design)
drops onto this directly.

### Run locally

```bash
# backend (terminal 1)
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                      # 11 synthetic-truth tests
.venv/bin/uvicorn app.main:app --port 8000

# frontend (terminal 2) — dev server proxies /api to :8000
cd frontend && npm install && npm run dev
```

Single-process (serve the built app from FastAPI): `cd frontend && npm run build`
then open the uvicorn server's root. Deploy is one Docker service (`Dockerfile`,
`render.yaml`).

### Configuration (env vars)

| var | default | purpose |
|---|---|---|
| `GENESCREEN_ALLOWED_ORIGINS` | "" (same-origin only) | comma-separated CORS allowlist |
| `GENESCREEN_RATE_MAX` / `_WINDOW` | 40 / 60 | per-IP request cap per window (seconds) on screen/dossier |
| `GENESCREEN_ALLOW_LIVE_OT` | 0 (off) | allow live Open Targets calls on cache miss; the bundled cache covers the whole demo subset, so leave off in production |

For local dev with live Open Targets (e.g. testing uploads), set
`GENESCREEN_ALLOW_LIVE_OT=1`.

### Rebuild the real demo subset (optional; subset is committed)

```bash
cd backend && bash scripts/fetch_depmap.sh && .venv/bin/python scripts/build_subset.py
```

## Data

DepMap 23Q4 Public (Broad Institute), via Figshare. Targetability will come from
the Open Targets Platform GraphQL API (`tractability`).
