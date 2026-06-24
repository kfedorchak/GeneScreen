import { useState, type ReactNode } from "react";
import type { DatasetInfo, ScreenParams } from "../types";
import HelpModal from "./HelpModal";

interface Props {
  dataset: DatasetInfo | null;
  params: ScreenParams;
  onChange: (p: ScreenParams) => void;
  onRun: () => void;
  loading: boolean;
}

export default function SetupPanel({ dataset, params, onChange, onRun, loading }: Props) {
  const [showHelp, setShowHelp] = useState(false);
  const set = <K extends keyof ScreenParams>(k: K, v: ScreenParams[K]) =>
    onChange({ ...params, [k]: v });

  return (
    <aside className="setup">
      <HelpModal open={showHelp} onClose={() => setShowHelp(false)} />
      <div className="setup-head">
        <h2>
          Screen setup
          <button
            className="info-btn"
            onClick={() => setShowHelp(true)}
            aria-label="Option definitions"
            title="Option definitions"
          >
            <svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true">
              <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1.4" />
              <circle cx="8" cy="4.6" r="0.95" fill="currentColor" />
              <rect x="7.2" y="6.6" width="1.6" height="5" rx="0.8" fill="currentColor" />
            </svg>
          </button>
        </h2>
        {dataset && (
          <p className="dataset-meta">
            <strong>{dataset.source}</strong>
            <br />
            {dataset.n_lines.toLocaleString()} lines · {dataset.n_drivers.toLocaleString()} CN
            drivers · {dataset.n_dependencies.toLocaleString()} dependencies ·{" "}
            {dataset.n_lineages} lineages
          </p>
        )}
      </div>

      <Group title="Test">
        <Seg
          label="Mode"
          value={params.mode}
          options={[
            ["continuous", "Continuous"],
            ["binary", "Binary"],
          ]}
          onChange={(v) => set("mode", v as ScreenParams["mode"])}
        />
        <Seg
          label="Direction"
          value={params.direction}
          options={[
            ["amplification", "Amplified"],
            ["deletion", "Deleted"],
            ["both", "Both"],
          ]}
          onChange={(v) => set("direction", v as ScreenParams["direction"])}
        />
        <Seg
          label="Relationship"
          value={params.relationship}
          options={[
            ["all", "All"],
            ["cis", "Cis"],
            ["trans", "Trans"],
          ]}
          onChange={(v) => set("relationship", v as ScreenParams["relationship"])}
        />
      </Group>

      {params.mode === "binary" && (
        <Group title="Binary thresholds">
          <Num label="Amplified CN ≥" value={params.amp_threshold} step={0.05} onChange={(v) => set("amp_threshold", v)} />
          <Num label="Deleted CN ≤" value={params.del_threshold} step={0.05} onChange={(v) => set("del_threshold", v)} />
          <Num label="Min group size" value={params.min_group_size} step={1} onChange={(v) => set("min_group_size", v)} />
        </Group>
      )}

      <Group title="Filters">
        <Toggle label="Exclude common essentials" hint="drop pan-lethal genes; keep selective deps" checked={params.exclude_common_essentials} onChange={(v) => set("exclude_common_essentials", v)} />
        <Toggle label="Lineage adjustment" hint="partial out OncotreeLineage confound" checked={params.lineage_adjust} onChange={(v) => set("lineage_adjust", v)} />
        <Num label="Min driver CN std" value={params.min_cn_std} step={0.02} onChange={(v) => set("min_cn_std", v)} />
      </Group>

      <Group title="Co-amplification">
        <Seg
          label="Handling"
          value={params.coamp_handling}
          options={[
            ["off", "Off"],
            ["flag", "Flag"],
            ["filter", "Filter"],
            ["control", "Control"],
          ]}
          onChange={(v) => set("coamp_handling", v as ScreenParams["coamp_handling"])}
        />
        {(params.coamp_handling === "filter") && (
          <Num label="Drop trans |CN corr| ≥" value={params.coamp_threshold} step={0.05} onChange={(v) => set("coamp_threshold", v)} />
        )}
        <Toggle label="Collapse amplicon modules" hint="group co-amplified drivers into one row" checked={params.collapse_amplicons} onChange={(v) => set("collapse_amplicons", v)} />
        {params.collapse_amplicons && (
          <Num label="Module CN corr ≥" value={params.amplicon_corr_threshold} step={0.05} onChange={(v) => set("amplicon_corr_threshold", v)} />
        )}
      </Group>

      <Group title="Significance">
        <Num label="FDR q ≤" value={params.fdr_threshold} step={0.01} onChange={(v) => set("fdr_threshold", v)} />
        <Num label="Max results" value={params.max_results} step={50} onChange={(v) => set("max_results", v)} />
      </Group>

      <button className="run-btn" onClick={onRun} disabled={loading}>
        {loading ? "Running screen…" : "Run screen"}
      </button>
    </aside>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="group">
      <div className="group-title">{title}</div>
      {children}
    </div>
  );
}

function Seg({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: [string, string][];
  onChange: (v: string) => void;
}) {
  return (
    <div className="control">
      <label>{label}</label>
      <div className="seg">
        {options.map(([v, l]) => (
          <button key={v} className={v === value ? "on" : ""} onClick={() => onChange(v)}>
            {l}
          </button>
        ))}
      </div>
    </div>
  );
}

function Num({
  label,
  value,
  step,
  onChange,
}: {
  label: string;
  value: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="control row">
      <label>{label}</label>
      <input
        type="number"
        value={value}
        step={step}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
    </div>
  );
}

function Toggle({
  label,
  hint,
  checked,
  onChange,
}: {
  label: string;
  hint?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="control toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>
        {label}
        {hint && <em>{hint}</em>}
      </span>
    </label>
  );
}
