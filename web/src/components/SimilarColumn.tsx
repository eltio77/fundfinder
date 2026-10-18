import type { CSSProperties } from "react";

import type { Mode, SearchResponse } from "../lib/api";
import { ms, ocf, score, scoreFill, siblingStats, clusterSize } from "../lib/format";
import { type RequestState, useMeta } from "../lib/hooks";
import { Fingerprint } from "./Fingerprint";
import { ErrorNote, Link, ScoreBar, Skeleton } from "./ui";

const COPY: Record<Mode, { title: string; blurb: string }> = {
  text: {
    title: "Text",
    blurb: "The fund's profile, embedded by Voyage, as the query.",
  },
  exposure: {
    title: "Exposure",
    blurb: "Cosine over sector, region and asset-class weights.",
  },
  both: {
    title: "Fused",
    blurb: "Reciprocal rank fusion of the two lists (k = 60).",
  },
};

interface Props {
  mode: Mode;
  state: RequestState<SearchResponse>;
  clusterId: string | null;
  showLabels: boolean;
  hovered: string | null;
  onHover: (id: string | null) => void;
}

export function SimilarColumn({ mode, state, clusterId, showLabels, hovered, onHover }: Props) {
  const meta = useMeta();
  const { data, error, loading, retryIn, reload } = state;
  const hits = data?.results ?? [];
  const stats = showLabels ? siblingStats(clusterId, clusterSize(clusterId), hits) : null;

  return (
    <section className={`col col-${mode}`} aria-labelledby={`col-${mode}`}>
      <header className="col-head">
        <h3 id={`col-${mode}`}>{COPY[mode].title}</h3>
        {stats && (
          <span
            className={`siblings ${stats.found === stats.total ? "all" : stats.found === 0 ? "none" : ""}`}
            title="Cluster siblings found in these results (synthetic test labels)"
          >
            {stats.found}/{stats.total} siblings
          </span>
        )}
        <p>{COPY[mode].blurb}</p>
        <p className="col-meta mono">
          {data && !loading
            ? `${ms(data.took_ms)} · ${data.exact ? "exact" : `nc ${data.num_candidates}`}`
            : " "}
        </p>
      </header>

      {error && !loading ? (
        <ErrorNote error={error} retryIn={null} onRetry={reload} />
      ) : error && retryIn !== null ? (
        <ErrorNote error={error} retryIn={retryIn} onRetry={reload} />
      ) : loading && !data ? (
        <Skeleton rows={6} />
      ) : hits.length === 0 ? (
        <p className="empty">No neighbours match these filters.</p>
      ) : (
        <ol className={`neighbours ${loading ? "is-stale" : ""}`}>
          {hits.map((h, i) => {
            const sibling = showLabels && clusterId !== null && h.cluster_id === clusterId;
            return (
              <li
                key={h.id}
                style={{ "--i": i } as CSSProperties}
                className={`${hovered === h.id ? "hl" : ""} ${sibling ? "sibling" : ""}`}
                onMouseEnter={() => onHover(h.id)}
                onMouseLeave={() => onHover(null)}
              >
                <span className="n-rank mono">{i + 1}</span>
                <div className="n-body">
                  <Link to={`/fund/${h.id}`} className="fund-link">
                    {h.name}
                  </Link>
                  <span className="sub">
                    {h.is_passive && <span className="tag">Index</span>}
                    {h.ia_sector} · <span className="mono">{ocf(h.ocf)}</span>
                  </span>
                  <span className="n-foot">
                    <Fingerprint vector={h.exposure_vector} layout={meta?.exposure_layout ?? null} />
                    {h.ranks && (
                      <span className="ranks mono" title="Rank in the text and exposure lists">
                        T{h.ranks.text ?? "–"} · E{h.ranks.exposure ?? "–"}
                      </span>
                    )}
                  </span>
                </div>
                <ScoreBar fill={scoreFill(h.score, mode)} label={score(h.score, mode)} />
                {sibling && (
                  <span className="sibling-mark" title="Same cluster as this fund">
                    ✓
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
