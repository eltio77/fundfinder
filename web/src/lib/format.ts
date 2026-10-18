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

/** Readable label for a synthetic cluster id, e.g. "trk_ftse100" -> "Tracker · ftse100". */
export function clusterLabel(id: string | null): string | null {
  if (!id) return null;
  const [kind, ...rest] = id.split("_");
  const name = rest.join(" ");
  const kinds: Record<string, string> = { trk: "Tracker", act: "Near-dupe", outlier: "Outlier" };
  return `${kinds[kind] ?? kind} · ${name}`;
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
