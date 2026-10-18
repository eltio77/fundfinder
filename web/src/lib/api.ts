export type Mode = "text" | "exposure" | "both";

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

export interface SearchResponse {
  query: string | null;
  fund_id: string | null;
  mode: Mode | null;
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

type Params = Record<string, string | number | boolean | null | undefined>;

export function toQuery(params: Params): string {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `?${s}` : "";
}

async function get<T>(path: string, params: Params = {}, signal?: AbortSignal): Promise<T> {
  const res = await fetch(path + toQuery(params), { signal });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* non-JSON error body */
    }
    const retry = res.headers.get("Retry-After");
    throw new ApiError(res.status, detail, retry ? Number(retry) : null);
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
  search: (q: string, filters: Filters, settings: SearchSettings, signal?: AbortSignal) =>
    get<SearchResponse>("/search", { q, ...searchParams(filters, settings) }, signal),
  similar: (
    id: string,
    mode: Mode,
    filters: Filters,
    settings: SearchSettings,
    signal?: AbortSignal,
  ) =>
    get<SearchResponse>(
      `/funds/${encodeURIComponent(id)}/similar`,
      { mode, ...searchParams(filters, settings) },
      signal,
    ),
};
