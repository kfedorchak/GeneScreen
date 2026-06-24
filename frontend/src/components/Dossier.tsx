import { useEffect, useState } from "react";
import { getDossier, getPairDetail } from "../api";
import type { Candidate, DossierReports, PairDetail, TractabilityBucket } from "../types";
import ScatterPlot from "./ScatterPlot";

interface Props {
  candidate: Candidate | null;
  onClose: () => void;
}

const MODALITY_LABEL: Record<string, string> = {
  SM: "Small molecule",
  AB: "Antibody",
  PR: "PROTAC",
  OC: "Other clinical",
};

export default function Dossier({ candidate, onClose }: Props) {
  const [detail, setDetail] = useState<PairDetail | null>(null);
  const [reports, setReports] = useState<DossierReports | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!candidate) return;
    setDetail(null);
    setReports(null);
    setErr(null);
    getPairDetail(candidate.driver_gene, candidate.dependency_gene)
      .then(setDetail)
      .catch((e) => setErr(String(e)));
    getDossier(
      candidate.driver_gene,
      candidate.dependency_gene,
      candidate.relationship,
      candidate.effect_size,
    )
      .then(setReports)
      .catch(() => {});
  }, [candidate]);

  if (!candidate) return null;
  const c = candidate;
  const isModule = c.module_size && c.module_size > 1;

  return (
    <div className="dossier-overlay" onClick={onClose}>
      <div className="dossier" onClick={(e) => e.stopPropagation()}>
        <button className="close" onClick={onClose}>
          ✕
        </button>

        <header>
          <h2>
            <span className="d-driver">{isModule ? c.module_label : c.driver_gene}</span>
            <span className="arrow">→</span>
            <span className="d-dep">{c.dependency_gene}</span>
            <span className={`rel ${c.relationship}`}>{c.relationship}</span>
          </h2>
          <p className="d-sub">
            Amplification of {isModule ? "this amplicon" : c.driver_gene} is associated with a
            stronger CRISPR dependency on {c.dependency_gene}.
          </p>
          {isModule && (
            <p className="d-module">
              <strong>Amplicon module ({c.module_size} co-amplified drivers):</strong>{" "}
              {c.module_members}
            </p>
          )}
        </header>

        <div className="stat-grid">
          <Stat label="Effect size" value={c.effect_size.toFixed(3)} sub={c.effect_metric} />
          <Stat label="FDR q-value" value={c.q_value < 1e-3 ? c.q_value.toExponential(1) : c.q_value.toFixed(3)} />
          <Stat label="Amplified in" value={`${(c.amp_frequency * 100).toFixed(0)}%`} sub="of lines" />
          <Stat label="Dependent in" value={`${(c.frac_dependent * 100).toFixed(0)}%`} sub="effect < −0.5" />
          <Stat label="CN correlation" value={c.cn_correlation === null ? "—" : c.cn_correlation.toFixed(2)} sub="driver vs dep CN" />
          <Stat label="Composite" value={(c.composite_score ?? 0).toFixed(2)} />
        </div>

        <section>
          <h3>Copy number vs. dependency across {detail?.points.length ?? "…"} lines</h3>
          {err && <p className="err">{err}</p>}
          {detail ? (
            <ScatterPlot points={detail.points} driver={c.driver_gene} dependency={c.dependency_gene} />
          ) : (
            !err && <p className="muted">loading plot…</p>
          )}
        </section>

        <section>
          <h3>Agent dossier</h3>
          <div className="agent-disclaimer">
            <strong>Targetability is live from Open Targets.</strong> Literature, precedent, and
            molecular design are <strong>simulated demonstration agents</strong> — their text,
            scores, and citations are illustrative placeholders, not real evidence. They share the
            same interface a live model would implement.
          </div>

          {!reports ? (
            <p className="muted">running agents…</p>
          ) : (
            <div className="agent-grid">
              {/* Targetability — live */}
              <div className="agent-card">
                <div className="agent-head">
                  <strong>Targetability</strong>
                  <span className="feeds live">Open Targets · live</span>
                </div>
                <ScoreBar value={reports.targetability.targetability_score} />
                <p>
                  {reports.targetability.top_modality
                    ? `Best tractability via ${reports.targetability.top_modality}.`
                    : "No tractability bucket passed — hard target."}
                  {reports.targetability.ensembl_id && (
                    <>
                      {" "}
                      <a
                        href={`https://platform.opentargets.org/target/${reports.targetability.ensembl_id}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {reports.targetability.ensembl_id}
                      </a>
                    </>
                  )}
                </p>
                <div className="buckets">
                  {topBuckets(reports.targetability.buckets).map((b) => (
                    <span key={`${b.modality}-${b.label}`} className={`bucket ${b.value ? "on" : ""}`}>
                      {MODALITY_LABEL[b.modality] ?? b.modality}: {b.label}
                    </span>
                  ))}
                </div>
              </div>

              {/* Literature */}
              <div className="agent-card">
                <div className="agent-head">
                  <strong>Literature research</strong>
                  <span className="feeds">feeds: Bio support · sim</span>
                </div>
                <ScoreBar value={reports.literature.support_score} />
                <p>{reports.literature.summary}</p>
                {reports.literature.citations.map((cit, i) => (
                  <div className="cite" key={i}>
                    {cit.title}
                    {cit.year ? ` · ${cit.year}` : ""}
                  </div>
                ))}
              </div>

              {/* Precedent */}
              <div className="agent-card">
                <div className="agent-head">
                  <strong>Precedent</strong>
                  <span className="feeds">feeds: Novelty · sim</span>
                </div>
                <ScoreBar value={reports.precedent.novelty_score} label="novelty" />
                <p>
                  <span className={`status ${reports.precedent.status}`}>{reports.precedent.status}</span>{" "}
                  {reports.precedent.summary}
                </p>
                {reports.precedent.programs.map((p, i) => (
                  <div className="cite" key={i}>
                    {p}
                  </div>
                ))}
              </div>

              {/* Molecular */}
              <div className="agent-card">
                <div className="agent-head">
                  <strong>Molecular design</strong>
                  <span className="feeds">sim</span>
                </div>
                <ScoreBar value={reports.molecular.feasibility_score} label="feasibility" />
                <p>{reports.molecular.summary}</p>
                <div className="buckets">
                  {reports.molecular.proposed_chemotypes.map((ch) => (
                    <span key={ch} className="bucket on">
                      {ch}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function topBuckets(buckets: TractabilityBucket[]): TractabilityBucket[] {
  // show passed buckets first, cap to keep the card tidy
  const passed = buckets.filter((b) => b.value);
  return (passed.length ? passed : buckets).slice(0, 6);
}

function ScoreBar({ value, label }: { value: number; label?: string }) {
  return (
    <div className="scorebar">
      <div className="scorebar-track">
        <div className="scorebar-fill" style={{ width: `${value * 100}%` }} />
      </div>
      <span>
        {value.toFixed(2)}
        {label ? ` ${label}` : ""}
      </span>
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}
