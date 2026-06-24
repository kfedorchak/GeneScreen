// Mirrors backend/app/schemas.py

export type Mode = "continuous" | "binary";
export type Direction = "amplification" | "deletion" | "both";
export type Relationship = "all" | "cis" | "trans";
export type CoampHandling = "off" | "flag" | "filter" | "control";

export interface ScreenParams {
  mode: Mode;
  direction: Direction;
  amp_threshold: number;
  del_threshold: number;
  min_group_size: number;
  min_cn_std: number;
  exclude_common_essentials: boolean;
  lineage_adjust: boolean;
  coamp_handling: CoampHandling;
  coamp_threshold: number;
  collapse_amplicons: boolean;
  amplicon_corr_threshold: number;
  fdr_threshold: number;
  relationship: Relationship;
  max_results: number;
}

export interface Candidate {
  driver_gene: string;
  dependency_gene: string;
  relationship: "cis" | "trans";
  n: number;
  effect_metric: string;
  effect_size: number;
  slope: number | null;
  p_value: number;
  q_value: number;
  amp_frequency: number;
  dep_selectivity: number;
  frac_dependent: number;
  cn_correlation: number | null;
  module_label: string | null;
  module_size: number | null;
  module_members: string | null;
  n_module_drivers: number | null;
  component_scores: Record<string, number>;
  composite_score: number | null;
}

export interface ScreenMeta {
  mode: string;
  direction: string;
  n_significant: number;
  collapsed: boolean;
  n_returned?: number;
  n_cis?: number;
  n_trans?: number;
}

export interface ScreenResponse {
  meta: ScreenMeta;
  candidates: Candidate[];
}

export interface DatasetInfo {
  source: string;
  n_lines: number;
  n_drivers: number;
  n_dependencies: number;
  n_common_essentials: number;
  n_lineages: number;
  lineages: string[];
}

export interface PairPoint {
  line: string;
  cn: number;
  effect: number;
  lineage: string;
}

export interface PairDetail {
  driver: string;
  dependency: string;
  points: PairPoint[];
}

export interface Citation {
  title: string;
  url: string | null;
  year: number | null;
  snippet: string | null;
}
export interface LiteratureReport {
  support_score: number;
  summary: string;
  citations: Citation[];
}
export interface PrecedentReport {
  novelty_score: number;
  status: "novel" | "emerging" | "crowded";
  summary: string;
  programs: string[];
}
export interface TractabilityBucket {
  label: string;
  modality: "SM" | "AB" | "PR" | "OC";
  value: boolean;
}
export interface TargetabilityReport {
  ensembl_id: string | null;
  targetability_score: number;
  top_modality: string | null;
  buckets: TractabilityBucket[];
}
export interface MolecularReport {
  feasibility_score: number;
  summary: string;
  proposed_chemotypes: string[];
}
export interface DossierReports {
  literature: LiteratureReport;
  precedent: PrecedentReport;
  targetability: TargetabilityReport;
  molecular: MolecularReport;
}

// The composite-score weights (client-side live re-ranking).
export interface Weights {
  effect: number;
  confidence: number;
  selectivity: number;
  prevalence: number;
  targetability: number;
  bio_support: number;
  novelty: number;
}

export const DEFAULT_WEIGHTS: Weights = {
  effect: 0.3,
  confidence: 0.2,
  selectivity: 0.15,
  prevalence: 0.1,
  targetability: 0.15,
  bio_support: 0.05,
  novelty: 0.05,
};

export const DEFAULT_PARAMS: ScreenParams = {
  mode: "continuous",
  direction: "amplification",
  amp_threshold: 1.3,
  del_threshold: 0.7,
  min_group_size: 10,
  min_cn_std: 0.1,
  exclude_common_essentials: true,
  lineage_adjust: false,
  coamp_handling: "flag",
  coamp_threshold: 0.6,
  collapse_amplicons: true,
  amplicon_corr_threshold: 0.7,
  fdr_threshold: 0.05,
  relationship: "all",
  max_results: 200,
};
