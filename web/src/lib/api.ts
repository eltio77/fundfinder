export type Mode = "text" | "exposure" | "both";
/** "auto": the server orders by cost when the query asks for low or high cost. */
export type Sort = "auto" | "relevance" | "cost" | "cost_desc";

export interface Hit {
  id: string;
  name: string;
  provider: string;
  ia_sector: string;
  asset_class: string;
  ocf: number;
  is_passive: boolean;
  tracked_index: string | null;
  cluster_id: string | null;
  exposure_vector: number[] | null;
  score: number;
  ranks: { text: number | null; exposure: number | null } | null;
}

/** One constraint the server read from the query; `key` goes back in `ignore`. */
export interface Understood {
  key: string;
  label: string;
}

export interface SearchResponse {
  query: string | null;
  fund_id: string | null;
  mode: Mode | null;
  sort: Exclude<Sort, "auto">;
  /** Only on /search: what was embedded and which constraints were applied. */
  interpretation: {
    /** "llm" when Claude read the query, "rules" for the standard reading. */
    source: "rules" | "llm";
    text: string;
    applied: Understood[];
    summary: string | null;
    notice: string | null;
    /** For "A or B": each text searched on its own, then merged. */
    alternatives?: string[];
  } | null;
  limit: number;
  num_candidates: number | null;
  exact: boolean;
  filters: Record<string, string | number | boolean>;
  took_ms: number;
  results: Hit[];
}

export interface Holding {
  name: string;
  weight: number;
}

export interface Fund {
  id: string;
  name: string;
  provider: string;
  ia_sector: string;
  asset_class: string;
  ocf: number;
  is_passive: boolean;
  tracked_index: string | null;
  objective: string;
  top_holdings: Holding[];
  sector_weights: Record<string, number>;
  region_weights: Record<string, number>;
  asset_class_weights: Record<string, number>;
  cluster_id: string | null;
  profile: string;
  exposure_vector: number[];
}

export interface ExposureLayout {
  sectors: string[];
  regions: string[];
  asset_classes: string[];
}

export interface Meta {
  ia_sectors: string[];
  asset_classes: string[];
  exposure_layout: ExposureLayout;
  embed_model: string;
  /** Whether "Interpret with AI" is available (the server has an Anthropic key). */
  llm_intent: { available: boolean; model: string | null };
  defaults: {
    limit: number;
    max_limit: number;
    candidates_per_result: number;
    max_num_candidates: number;
  };
}

export interface Filters {
  asset_class?: string;
  ia_sector?: string;
  ocf_max?: number;
  is_passive?: boolean;
}

export interface SearchSettings {
  limit: number;
  numCandidates: number | null; // null = server default (20 x limit)
  exact: boolean;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    readonly retryAfter: number | null = null,
  ) {
    super(message);
  }

  get rateLimited(): boolean {
    return this.status === 429;
  }
}

const MAX_RETRY_AFTER_S = 120;

/**
 * Retry-After is either delay-seconds or an HTTP date. Returns whole seconds
 * clamped to 1..120, or null when absent or unparseable, so an odd header can't
 * stall the retry countdown (NaN never reaches 0) or push it hours away.
 */
export function parseRetryAfter(value: string | null, now: number = Date.now()): number | null {
  const v = value?.trim();
  if (!v) return null;
  let seconds: number;
  if (/^\d+$/.test(v)) {
    seconds = Number(v);
  } else {
    // An HTTP date names its day and month; Date.parse alone would read "-5" as a year.
    const at = /[a-z]/i.test(v) ? Date.parse(v) : NaN;
    if (Number.isNaN(at)) return null;
    seconds = Math.ceil((at - now) / 1000);
  }
  return Math.min(MAX_RETRY_AFTER_S, Math.max(1, seconds));
}

type Scalar = string | number | boolean | null | undefined;
type Params = Record<string, Scalar | string[]>;

/** Arrays become repeated keys (?ignore=a&ignore=b). */
export function toQuery(params: Params): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    for (const item of Array.isArray(v) ? v : [v]) {
      if (item !== undefined && item !== null && item !== "")
        qs.append(k, String(item));
    }
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

async function get<T>(
  path: string,
  params: Params = {},
  signal?: AbortSignal,
): Promise<T> {
  const res = await fetch(path + toQuery(params), { signal });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body: { detail?: unknown } = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (body.detail !== undefined) detail = JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail, parseRetryAfter(res.headers.get("Retry-After")));
  }
  return res.json() as Promise<T>;
}

function searchParams(filters: Filters, settings: SearchSettings): Params {
  return {
    ...filters,
    limit: settings.limit,
    num_candidates: settings.exact ? null : settings.numCandidates,
    exact: settings.exact || null,
  };
}

export interface ClusterMember {
  id: string;
  name: string;
}

export const api = {
  meta: (signal?: AbortSignal) => get<Meta>("/meta", {}, signal),
  clusters: (signal?: AbortSignal) =>
    get<Record<string, ClusterMember[]>>("/clusters", {}, signal),
  fund: (id: string, signal?: AbortSignal) =>
    get<Fund>(`/funds/${encodeURIComponent(id)}`, {}, signal),
  search: (
    q: string,
    sort: Sort,
    ignore: string[],
    ai: boolean,
    filters: Filters,
    settings: SearchSettings,
    signal?: AbortSignal,
  ) =>
    get<SearchResponse>(
      "/search",
      {
        q,
        sort: sort === "auto" ? null : sort,
        ignore,
        intent: ai ? "llm" : null,
        ...searchParams(filters, settings),
      },
      signal,
    ),
  similar: (
    id: string,
    mode: Mode,
    filters: Filters,
    settings: SearchSettings,
    signal?: AbortSignal,
    sort: Exclude<Sort, "auto"> = "relevance",
  ) =>
    get<SearchResponse>(
      `/funds/${encodeURIComponent(id)}/similar`,
      {
        mode,
        sort: sort === "relevance" ? null : sort,
        ...searchParams(filters, settings),
      },
      signal,
    ),
};

/** Shown when AI mode was busy or down and the standard reading was used instead. */
export const AI_FALLBACK_NOTICE =
  "AI interpretation is busy right now, so the standard reading of your words was used. Try again in a minute.";

/**
 * AI mode is best effort: when the AI search is rate limited (429) or unavailable
 * (503), search again with the standard reading and say so, rather than showing
 * an error or a long retry countdown. Other errors, and failures of the standard
 * search itself (e.g. an embedding 429, retried by useRequest), propagate.
 */
export async function withAiFallback(
  ai: boolean,
  run: (ai: boolean) => Promise<SearchResponse>,
): Promise<SearchResponse> {
  if (!ai) return run(false);
  try {
    return await run(true);
  } catch (e) {
    if (!(e instanceof ApiError) || (e.status !== 429 && e.status !== 503)) throw e;
    const res = await run(false);
    return res.interpretation
      ? { ...res, interpretation: { ...res.interpretation, notice: AI_FALLBACK_NOTICE } }
      : res;
  }
}
