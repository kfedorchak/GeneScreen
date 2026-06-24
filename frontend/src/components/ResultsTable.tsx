import type { Candidate } from "../types";

interface Props {
  candidates: Candidate[];
  composites: number[]; // parallel to candidates, live composite
  onSelect: (c: Candidate) => void;
  selected: Candidate | null;
}

function fmt(x: number | null, d = 2): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "—";
  return x.toFixed(d);
}

function qfmt(q: number): string {
  if (q === 0) return "0";
  if (q < 1e-3) return q.toExponential(1);
  return q.toFixed(3);
}

export default function ResultsTable({ candidates, composites, onSelect, selected }: Props) {
  return (
    <div className="table-wrap">
      <table className="results">
        <thead>
          <tr>
            <th>#</th>
            <th>Driver / amplicon</th>
            <th>Dependency</th>
            <th>Rel.</th>
            <th>Effect</th>
            <th>q</th>
            <th>CN corr</th>
            <th>Amp freq</th>
            <th>Composite</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c, i) => {
            const isSel =
              selected &&
              selected.driver_gene === c.driver_gene &&
              selected.dependency_gene === c.dependency_gene;
            const moduleN = c.module_size && c.module_size > 1 ? c.module_size : 0;
            return (
              <tr
                key={`${c.driver_gene}->${c.dependency_gene}`}
                className={isSel ? "sel" : ""}
                onClick={() => onSelect(c)}
              >
                <td className="rank">{i + 1}</td>
                <td className="gene">
                  {moduleN ? (
                    <span title={c.module_members ?? ""}>
                      {c.module_label}
                      <span className="modchip">{moduleN} genes</span>
                    </span>
                  ) : (
                    c.driver_gene
                  )}
                </td>
                <td className="gene dep">{c.dependency_gene}</td>
                <td>
                  <span className={`rel ${c.relationship}`}>{c.relationship}</span>
                </td>
                <td className="num">{fmt(c.effect_size, 3)}</td>
                <td className="num">{qfmt(c.q_value)}</td>
                <td className="num">{fmt(c.cn_correlation, 2)}</td>
                <td className="num">{(c.amp_frequency * 100).toFixed(0)}%</td>
                <td>
                  <div className="bar">
                    <div className="bar-fill" style={{ width: `${composites[i] * 100}%` }} />
                    <span>{fmt(composites[i], 2)}</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
