import type { Filters, SearchSettings, Sort } from "./api";

export const DEFAULT_LIMIT = 10;

// Mirror the API's bounds (fundfinder/routes/api.py, search.py) so a hand-edited or
// shared URL falls back to defaults instead of sending values the API rejects (422).
const MAX_QUERY_LENGTH = 2000;
const MAX_LIMIT = 100;
const MAX_NUM_CANDIDATES = 10_000;
const MAX_IGNORED = 50;

/** A whole number in [min, max], else undefined. */
function intIn(v: number | undefined, min: number, max: number): number | undefined {
  return v !== undefined && Number.isInteger(v) && v >= min && v <= max ? v : undefined;
}

/** Read filters + settings from URL params (search page state lives in the URL). */
export function readQuery(params: URLSearchParams): {
  q: string;
  sort: Sort;
  /** Understood-constraint keys the user removed (see SearchResponse.interpretation). */
  ignore: string[];
  /** "Interpret with AI" mode (?intent=llm); off by default. */
  ai: boolean;
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
  const ocfMax = num("ocf_max");
  return {
    q: (params.get("q") ?? "").slice(0, MAX_QUERY_LENGTH),
    sort: sort === "relevance" || sort === "cost" || sort === "cost_desc" ? sort : "auto",
    ignore: [...new Set(params.getAll("ignore").filter(Boolean))].slice(0, MAX_IGNORED),
    ai: params.get("intent") === "llm",
    filters: {
      asset_class: params.get("asset_class") || undefined,
      ia_sector: params.get("ia_sector") || undefined,
      ocf_max: ocfMax !== undefined && ocfMax >= 0 ? ocfMax : undefined,
      is_passive: passive === "true" ? true : passive === "false" ? false : undefined,
    },
    settings: {
      limit: intIn(num("limit"), 1, MAX_LIMIT) ?? DEFAULT_LIMIT,
      numCandidates: intIn(num("nc"), 1, MAX_NUM_CANDIDATES) ?? null,
      exact: params.get("exact") === "true",
    },
  };
}

export function writeQuery(
  q: string,
  filters: Filters,
  settings: SearchSettings,
  sort: Sort = "auto",
  ignore: string[] = [],
  ai = false,
): string {
  const p = new URLSearchParams();
  if (q) p.set("q", q);
  if (ai) p.set("intent", "llm");
  if (sort !== "auto") p.set("sort", sort);
  for (const k of ignore) p.append("ignore", k);
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
