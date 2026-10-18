import type { Filters, SearchSettings, Sort } from "./api";

export const DEFAULT_LIMIT = 10;

/** Read filters + settings from URL params (search page state lives in the URL). */
export function readQuery(params: URLSearchParams): {
  q: string;
  sort: Sort;
  filters: Filters;
  settings: SearchSettings;
} {
  const num = (k: string) => {
    const v = params.get(k);
    if (v === null || v === "") return undefined;
    const n = Number(v);
    return Number.isFinite(n) ? n : undefined;
  };
  const passive = params.get("is_passive");
  const sort = params.get("sort");
  return {
    q: params.get("q") ?? "",
    sort: sort === "relevance" || sort === "cost" ? sort : "auto",
    filters: {
      asset_class: params.get("asset_class") || undefined,
      ia_sector: params.get("ia_sector") || undefined,
      ocf_max: num("ocf_max"),
      is_passive: passive === "true" ? true : passive === "false" ? false : undefined,
    },
    settings: {
      limit: num("limit") ?? DEFAULT_LIMIT,
      numCandidates: num("nc") ?? null,
      exact: params.get("exact") === "true",
    },
  };
}

export function writeQuery(
  q: string,
  filters: Filters,
  settings: SearchSettings,
  sort: Sort = "auto",
): string {
  const p = new URLSearchParams();
  if (q) p.set("q", q);
  if (sort !== "auto") p.set("sort", sort);
  if (filters.asset_class) p.set("asset_class", filters.asset_class);
  if (filters.ia_sector) p.set("ia_sector", filters.ia_sector);
  if (filters.ocf_max !== undefined) p.set("ocf_max", String(filters.ocf_max));
  if (filters.is_passive !== undefined) p.set("is_passive", String(filters.is_passive));
  if (settings.limit !== DEFAULT_LIMIT) p.set("limit", String(settings.limit));
  if (settings.numCandidates !== null) p.set("nc", String(settings.numCandidates));
  if (settings.exact) p.set("exact", "true");
  const s = p.toString();
  return s ? `?${s}` : "";
}
