interface Props {
  open: boolean;
  onClose: () => void;
}

interface Item {
  term: string;
  def: string;
}
interface Section {
  title: string;
  items: Item[];
}

const SECTIONS: Section[] = [
  {
    title: "Test",
    items: [
      {
        term: "Mode — Continuous",
        def: "Correlate each driver's copy number (as a continuous value) against each dependency's gene effect across all cell lines (Spearman). Uses every line, no threshold needed.",
      },
      {
        term: "Mode — Binary",
        def: "Split lines into amplified vs. not by a copy-number threshold, then test whether the dependency differs between the two groups (Mann–Whitney U, effect size = Cliff's delta).",
      },
      {
        term: "Direction — Amplified / Deleted / Both",
        def: "Which copy-number change you hypothesise induces the dependency: gain (amplified), loss (deleted), or either. A hit means the change tracks with a stronger dependency (more negative gene effect).",
      },
      {
        term: "Relationship — All / Cis / Trans",
        def: "Cis = the driver gene IS the dependency (oncogene addiction) — or, with amplicon collapse on, the dependency lies in the driver's amplicon. Trans = driver and dependency are different loci (candidate novel relationships). All = both.",
      },
    ],
  },
  {
    title: "Binary thresholds (binary mode only)",
    items: [
      {
        term: "Amplified CN ≥",
        def: "Copy-number value at/above which a line counts as amplified. Scale is log2(relative CN + 1), where diploid ≈ 1.0 (so ~1.3+ is a gain).",
      },
      {
        term: "Deleted CN ≤",
        def: "Copy-number value at/below which a line counts as deleted (homozygous loss ≈ 0).",
      },
      {
        term: "Min group size",
        def: "Minimum number of lines in the smaller (amplified/deleted) group for a test to run — guards against calling significance off a handful of lines.",
      },
    ],
  },
  {
    title: "Filters",
    items: [
      {
        term: "Exclude common essentials",
        def: "Drop genes essential in virtually every line (ribosome, proteasome, spliceosome…). These are toxic to normal cells and not selective opportunities; removing them keeps the hits selective dependencies.",
      },
      {
        term: "Lineage adjustment",
        def: "Remove the part of copy number and of gene effect explained by tissue type, then correlate the residuals — so a hit must hold within tissues, not just because both are common in the same lineage. Conservative: guards against tissue-confounded false positives but can wash out genuine tissue-restricted biology.",
      },
      {
        term: "Min driver CN std",
        def: "Drop copy-number genes that barely vary across lines — they carry no signal and only add to the multiple-testing burden.",
      },
    ],
  },
  {
    title: "Co-amplification",
    items: [
      {
        term: "Handling — Off / Flag / Filter / Control",
        def: "How to treat a trans hit whose driver copy number tracks the dependency's OWN copy number (same amplicon). Off: ignore. Flag: annotate the CN correlation, change nothing. Filter: drop trans pairs above the threshold. Control: statistically partial out the dependency's own copy number so passenger signal collapses.",
      },
      {
        term: "Drop trans |CN corr| ≥",
        def: "For Filter mode: the driver-vs-dependency copy-number correlation above which a trans pair is treated as a co-amplicon passenger and dropped.",
      },
      {
        term: "Collapse amplicon modules",
        def: "Group co-amplified drivers (statistically indistinguishable) into one amplicon module and show a single representative row per dependency, listing the members — instead of a dozen near-identical rows.",
      },
      {
        term: "Module CN corr ≥",
        def: "Copy-number correlation above which two drivers are considered part of the same amplicon module.",
      },
    ],
  },
  {
    title: "Significance",
    items: [
      {
        term: "FDR q ≤",
        def: "Benjamini–Hochberg false-discovery-rate cutoff across all tested pairs. Lower = stricter (fewer, higher-confidence hits).",
      },
      {
        term: "Max results",
        def: "Cap on the number of ranked rows returned.",
      },
    ],
  },
];

export default function HelpModal({ open, onClose }: Props) {
  if (!open) return null;
  return (
    <div className="help-overlay" onClick={onClose}>
      <div className="help-modal" onClick={(e) => e.stopPropagation()}>
        <button className="close" onClick={onClose}>
          ✕
        </button>
        <h2>Screen options</h2>
        <p className="help-intro">
          Each driver (copy number, Dataset A) is screened against each dependency (CRISPR gene
          effect, Dataset B). A negative effect means more copies track with a stronger dependency.
        </p>
        {SECTIONS.map((s) => (
          <section key={s.title}>
            <h3>{s.title}</h3>
            <dl>
              {s.items.map((it) => (
                <div className="help-item" key={it.term}>
                  <dt>{it.term}</dt>
                  <dd>{it.def}</dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>
    </div>
  );
}
