import type {
  Candidate,
  DatasetInfo,
  DossierReports,
  PairDetail,
  ScreenParams,
  ScreenResponse,
  Weights,
} from "./types";

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export function getDataset(): Promise<DatasetInfo> {
  return fetch("/api/dataset").then((r) => jsonOrThrow<DatasetInfo>(r));
}

export function runScreen(params: ScreenParams): Promise<ScreenResponse> {
  return fetch("/api/screen", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  }).then((r) => jsonOrThrow<ScreenResponse>(r));
}

export function getPairDetail(driver: string, dependency: string): Promise<PairDetail> {
  const q = new URLSearchParams({ driver, dependency });
  return fetch(`/api/pair_detail?${q}`).then((r) => jsonOrThrow<PairDetail>(r));
}

export function getDossier(
  driver: string,
  dependency: string,
  relationship: string,
  effectSize: number,
): Promise<DossierReports> {
  const q = new URLSearchParams({
    driver,
    dependency,
    relationship,
    effect_size: String(effectSize),
  });
  return fetch(`/api/dossier?${q}`).then((r) => jsonOrThrow<DossierReports>(r));
}

// Client-side composite recomputation for live re-ranking. Mirrors
// scoring.composite_score: weighted mean of 0-1 component scores, with the
// novelty preference flipping novelty around its neutral point.
export function recomputeComposite(
  c: Candidate,
  weights: Weights,
  noveltyPreference: number,
): number {
  const cs = c.component_scores || {};
  const adjusted: Record<string, number> = {
    ...cs,
    novelty: 0.5 + noveltyPreference * ((cs.novelty ?? 0.5) - 0.5),
  };
  let num = 0;
  let den = 0;
  for (const [k, w] of Object.entries(weights)) {
    num += w * (adjusted[k] ?? 0.5);
    den += w;
  }
  const v = den > 0 ? num / den : 0;
  return Math.max(0, Math.min(1, v));
}
