import {
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { PairPoint } from "../types";

interface Props {
  points: PairPoint[];
  driver: string;
  dependency: string;
}

// A small palette; lineages beyond it fall back to grey.
const PALETTE = [
  "#2563eb", "#dc2626", "#16a34a", "#d97706", "#7c3aed", "#0891b2",
  "#db2777", "#65a30d", "#ea580c", "#4f46e5", "#0d9488", "#9333ea",
];

export default function ScatterPlot({ points, driver, dependency }: Props) {
  const lineages = Array.from(new Set(points.map((p) => p.lineage))).sort();
  const color = (l: string) => {
    const i = lineages.indexOf(l);
    return i >= 0 && i < PALETTE.length ? PALETTE[i] : "#9aa3b2";
  };

  return (
    <div className="scatter">
      <ResponsiveContainer width="100%" height={300}>
        <ScatterChart margin={{ top: 10, right: 16, bottom: 28, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e6e8ee" />
          <XAxis
            type="number"
            dataKey="cn"
            name="copy number"
            tick={{ fontSize: 11 }}
            label={{ value: `${driver} copy number  (log2(CN+1), diploid=1)`, position: "bottom", offset: 12, fontSize: 11 }}
          />
          <YAxis
            type="number"
            dataKey="effect"
            name="gene effect"
            tick={{ fontSize: 11 }}
            label={{ value: `${dependency} gene effect`, angle: -90, position: "insideLeft", fontSize: 11 }}
          />
          <ZAxis range={[26, 26]} />
          <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="4 4" />
          <ReferenceLine y={-1} stroke="#f0abab" strokeDasharray="4 4" label={{ value: "common-essential", fontSize: 9, fill: "#c05656", position: "insideTopLeft" }} />
          <ReferenceLine x={1} stroke="#cbd5e1" strokeDasharray="4 4" />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            content={({ active, payload }) => {
              if (!active || !payload || !payload.length) return null;
              const p = payload[0].payload as PairPoint;
              return (
                <div className="tip">
                  <strong>{p.line}</strong>
                  <div>{p.lineage}</div>
                  <div>CN {p.cn.toFixed(2)} · effect {p.effect.toFixed(2)}</div>
                </div>
              );
            }}
          />
          <Scatter data={points} fillOpacity={0.7}>
            {points.map((p, i) => (
              <Cell key={i} fill={color(p.lineage)} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
