import { useEffect, useMemo, useState } from "react";
import { getDataset, recomputeComposite, runScreen } from "./api";
import Dossier from "./components/Dossier";
import ResultsTable from "./components/ResultsTable";
import SetupPanel from "./components/SetupPanel";
import WeightSliders from "./components/WeightSliders";
import {
  DEFAULT_PARAMS,
  DEFAULT_WEIGHTS,
  type Candidate,
  type DatasetInfo,
  type ScreenParams,
  type ScreenResponse,
  type Weights,
} from "./types";

export default function App() {
  const [dataset, setDataset] = useState<DatasetInfo | null>(null);
  const [params, setParams] = useState<ScreenParams>(DEFAULT_PARAMS);
  const [response, setResponse] = useState<ScreenResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [weights, setWeights] = useState<Weights>(DEFAULT_WEIGHTS);
  const [noveltyPref, setNoveltyPref] = useState(1);
  const [selected, setSelected] = useState<Candidate | null>(null);

  useEffect(() => {
    getDataset().then(setDataset).catch((e) => setError(String(e)));
  }, []);

  const run = async () => {
    setLoading(true);
    setError(null);
    setSelected(null);
    try {
      const r = await runScreen(params);
      setResponse(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  // Live re-rank: recompute composite client-side and sort.
  const ranked = useMemo(() => {
    if (!response) return { candidates: [] as Candidate[], composites: [] as number[] };
    const withScore = response.candidates.map((c) => ({
      c,
      score: recomputeComposite(c, weights, noveltyPref),
    }));
    withScore.sort((a, b) => b.score - a.score);
    return {
      candidates: withScore.map((x) => x.c),
      composites: withScore.map((x) => x.score),
    };
  }, [response, weights, noveltyPref]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">⊕</span> GeneScreen
        </div>
        <div className="tagline">Copy-number–associated dependency discovery · DepMap</div>
      </header>

      <div className="layout">
        <SetupPanel
          dataset={dataset}
          params={params}
          onChange={setParams}
          onRun={run}
          loading={loading}
        />

        <main className="results-area">
          {error && <div className="banner err">{error}</div>}

          {!response && !loading && (
            <div className="empty">
              <h1>Find genes that become essential when another gene is amplified.</h1>
              <p>
                Each row of DepMap copy-number data (Dataset A) is screened against every CRISPR
                gene-effect column (Dataset B). Configure the screen and hit{" "}
                <strong>Run screen</strong>. Known oncogene-addiction relationships (ERBB2, CCND1,
                MDM2…) surface as a built-in positive control.
              </p>
            </div>
          )}

          {loading && <div className="empty">Running screen across all gene pairs…</div>}

          {response && !loading && (
            <>
              <div className="result-meta">
                <span className="pill strong">
                  {response.meta.n_significant.toLocaleString()} hits
                </span>
                <span className="pill cis">{response.meta.n_cis ?? 0} cis</span>
                <span className="pill trans">{response.meta.n_trans ?? 0} trans</span>
                {response.meta.collapsed && <span className="pill">amplicon-collapsed</span>}
                <span className="pill ghost">
                  {response.meta.mode} · {response.meta.direction}
                </span>
              </div>

              <WeightSliders
                weights={weights}
                onChange={setWeights}
                noveltyPreference={noveltyPref}
                onNoveltyChange={setNoveltyPref}
              />

              {ranked.candidates.length === 0 ? (
                <div className="empty">No pairs passed the significance threshold.</div>
              ) : (
                <ResultsTable
                  candidates={ranked.candidates}
                  composites={ranked.composites}
                  onSelect={setSelected}
                  selected={selected}
                />
              )}
            </>
          )}
        </main>
      </div>

      <Dossier candidate={selected} onClose={() => setSelected(null)} />

      <footer className="site-footer">
        <p>
          <strong>Research &amp; demonstration use only — not for clinical decision-making.</strong>{" "}
          Hypothesis-generating analysis of public cell-line data; findings are not validated.
        </p>
        <p>
          Data: dependency &amp; copy-number from{" "}
          <a href="https://depmap.org/portal/" target="_blank" rel="noreferrer">
            DepMap 23Q4 (Broad Institute)
          </a>
          , CC BY 4.0. Target tractability from{" "}
          <a href="https://platform.opentargets.org/" target="_blank" rel="noreferrer">
            Open Targets Platform
          </a>
          . Literature / precedent / molecular-design panels are simulated demonstrations.
        </p>
      </footer>
    </div>
  );
}
