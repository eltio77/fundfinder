import type { Hit, Mode } from "./api";

export const pct = (w: number, digits = 1): string => `${(w * 100).toFixed(digits)}%`;

/** OCF is stored in percent already (0.12 means 0.12%). */
export const ocf = (v: number): string => `${v.toFixed(2)}%`;

export const ms = (v: number): string => (v < 1000 ? `${Math.round(v)} ms` : `${(v / 1000).toFixed(2)} s`);

export function score(v: number, mode: Mode | null): string {
  return mode === "both" ? v.toFixed(4) : v.toFixed(3);
}

/** Bar fill (0..1) with an absolute meaning, so bars are comparable across lists.
 *  Atlas reports cosine as (1 + cos) / 2, so 0.5 means unrelated and 1 identical.
 *  RRF over two lists (k = 60) peaks at 2 / 61, when an item is first in both. */
export const RRF_MAX = 2 / 61;

export function scoreFill(v: number, mode: Mode | null): number {
  const fill = mode === "both" ? v / RRF_MAX : (v - 0.5) * 2;
  return Math.max(0.03, Math.min(1, fill));
}

const CLUSTER_NAMES: Record<string, string> = {
  trk_ftse100: "FTSE 100",
  trk_ftse_allshare: "FTSE All-Share",
  trk_ftse_gilts: "UK Gilts",
  trk_global_agg: "Global Aggregate",
  trk_msci_world: "MSCI World",
  trk_sp500: "S&P 500",
  act_uk_income: "UK Equity Income",
  act_global_tech: "Global Technology",
  act_uk_smaller: "UK Smaller Companies",
  act_strat_bond: "Strategic Bond",
  act_japan_value: "Japan Value",
  outlier_gold: "Gold Miners",
  outlier_frontier: "Frontier Markets",
  outlier_india: "India",
  outlier_biotech: "Biotechnology",
  outlier_direct_property: "UK Direct Property",
};

const CLUSTER_KINDS: Record<string, string> = { trk: "Tracker", act: "Near-dupe", outlier: "Outlier" };

/** Human name for a synthetic cluster id, e.g. "trk_sp500" -> "S&P 500". */
export function clusterName(id: string): string {
  return CLUSTER_NAMES[id] ?? id.split("_").slice(1).join(" ");
}

/** "Kind · name", e.g. "trk_ftse100" -> "Tracker · FTSE 100". */
export function clusterLabel(id: string | null): string | null {
  if (!id) return null;
  const kind = id.split("_")[0];
  return `${CLUSTER_KINDS[kind] ?? kind} · ${clusterName(id)}`;
}

export interface SiblingStats {
  found: number;
  total: number;
}

/** How many of the query fund's cluster siblings appear in the results. */
export function siblingStats(
  clusterId: string | null,
  clusterSize: number,
  hits: Pick<Hit, "cluster_id">[],
): SiblingStats | null {
  if (!clusterId || clusterSize <= 1) return null;
  return {
    found: hits.filter((h) => h.cluster_id === clusterId).length,
    total: clusterSize - 1,
  };
}

/** Expected cluster size, from the synthetic generator's design. */
export function clusterSize(clusterId: string | null): number {
  if (!clusterId) return 0;
  if (clusterId.startsWith("trk_")) return 5;
  if (clusterId.startsWith("act_")) return 4;
  return 1;
}

/** Scale an exposure vector to 0..1 by its own maximum, for display intensity. */
export function intensities(vec: number[]): number[] {
  const max = Math.max(...vec, 0);
  return max > 0 ? vec.map((v) => v / max) : vec.map(() => 0);
}

export type Strength = "strong" | "good" | "weak";

/** Plain-language match strength for a single-method score (Atlas cosine 0.5..1). */
export function strength(score: number): Strength {
  const fill = (score - 0.5) * 2;
  return fill >= 0.45 ? "strong" : fill >= 0.28 ? "good" : "weak";
}

export const STRENGTH_LABEL: Record<Strength, string> = {
  strong: "Strong match",
  good: "Good match",
  weak: "Loose match",
};

/** Why a fused result was matched, from its ranks in the two underlying lists.
 *  "Both" only counts when the fund is in the top `depth` of each list (the lists
 *  themselves are fetched deeper, so mere presence in both says little). */
export function matchReason(
  ranks: { text: number | null; exposure: number | null } | null,
  depth: number,
): { label: string; strength: Strength; both: boolean } {
  if (!ranks) return { label: "Similar fund", strength: "good", both: false };
  const t = ranks.text !== null && ranks.text <= depth ? ranks.text : null;
  const e = ranks.exposure !== null && ranks.exposure <= depth ? ranks.exposure : null;
  if (t !== null && e !== null)
    return { label: "Similar description and holdings", strength: "strong", both: true };
  const byText = (ranks.text ?? Infinity) <= (ranks.exposure ?? Infinity);
  return {
    label: byText ? "Similar description" : "Similar holdings",
    strength: t !== null || e !== null ? "good" : "weak",
    both: false,
  };
}
