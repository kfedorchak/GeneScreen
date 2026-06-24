import { DEFAULT_WEIGHTS, type Weights } from "../types";

const DEFAULT_NOVELTY = 1;

interface Props {
  weights: Weights;
  onChange: (w: Weights) => void;
  noveltyPreference: number;
  onNoveltyChange: (v: number) => void;
}

const LABELS: Record<keyof Weights, string> = {
  effect: "Effect size",
  confidence: "Confidence",
  selectivity: "Selectivity",
  prevalence: "Prevalence",
  targetability: "Targetability",
  bio_support: "Bio support",
  novelty: "Novelty",
};

const AGENT_KEYS = new Set(["targetability", "bio_support", "novelty"]);

export default function WeightSliders({
  weights,
  onChange,
  noveltyPreference,
  onNoveltyChange,
}: Props) {
  const isDefault =
    noveltyPreference === DEFAULT_NOVELTY &&
    (Object.keys(DEFAULT_WEIGHTS) as (keyof Weights)[]).every(
      (k) => weights[k] === DEFAULT_WEIGHTS[k],
    );

  const reset = () => {
    onChange({ ...DEFAULT_WEIGHTS });
    onNoveltyChange(DEFAULT_NOVELTY);
  };

  return (
    <div className="weights">
      <div className="weights-head">
        <div className="weights-title">Composite weights — re-ranks live</div>
        <button className="reset-btn" onClick={reset} disabled={isDefault}>
          Reset
        </button>
      </div>
      <div className="weights-grid">
        {(Object.keys(LABELS) as (keyof Weights)[]).map((k) => (
          <div className="wslider" key={k}>
            <label>
              {LABELS[k]}
              {AGENT_KEYS.has(k) && <span className="agent-tag" title="from an agent (stubbed)">agent</span>}
              <b>{weights[k].toFixed(2)}</b>
            </label>
            <input
              type="range"
              min={0}
              max={0.5}
              step={0.01}
              value={weights[k]}
              onChange={(e) => onChange({ ...weights, [k]: parseFloat(e.target.value) })}
            />
          </div>
        ))}
        <div className="wslider novelty">
          <label>
            Novelty preference
            <b>{noveltyPreference > 0 ? "discover" : noveltyPreference < 0 ? "de-risk" : "neutral"}</b>
          </label>
          <input
            type="range"
            min={-1}
            max={1}
            step={0.5}
            value={noveltyPreference}
            onChange={(e) => onNoveltyChange(parseFloat(e.target.value))}
          />
        </div>
      </div>
    </div>
  );
}
