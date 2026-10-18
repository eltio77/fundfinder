import type { Mode, SearchResponse } from "../lib/api";
import { clusterSize, ms, score, scoreFill, siblingStats } from "../lib/format";
import { type RequestState, useMeta } from "../lib/hooks";
import { fundPath } from "../lib/router";
import { Fingerprint } from "./Fingerprint";
import { ErrorNote, Link, Num, ScoreBar, Skeleton } from "./ui";

const COPY: Record<Mode, { title: string; blurb: string; tone: string }> = {
  text: { title: "Text", blurb: "Profile embedded by Voyage, used as the query", tone: "forest" },
  exposure: { title: "Exposure", blurb: "Cosine over sector, region and asset weights", tone: "cream" },
  both: { title: "Fused", blurb: "Reciprocal rank fusion of both lists", tone: "lilac" },
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
  const copy = COPY[mode];

  return (
    <section className="ncol" aria-labelledby={`col-${mode}`}>
      <header className="ncol-head">
        <div className="ncol-title">
          <span className={`dot sw-${copy.tone}`} />
          <h4 id={`col-${mode}`}>{copy.title}</h4>
          {stats && (
            <span
              className={`pill ${stats.found === stats.total ? "pill-green" : stats.found === 0 ? "pill-coral" : "pill-amber"}`}
              title="Designed cluster siblings found in these results"
            >
              {stats.found}/{stats.total} siblings
            </span>
          )}
        </div>
        <p className="muted small">{copy.blurb}</p>
        <p className="ncol-meta">
          {data && !loading
            ? `${ms(data.took_ms)} · ${data.exact ? "exact" : `nc ${data.num_candidates}`}`
            : " "}
        </p>
      </header>

      {error && (retryIn !== null || !loading) ? (
        <ErrorNote error={error} retryIn={retryIn} onRetry={reload} />
      ) : loading && !data ? (
        <Skeleton rows={6} />
      ) : hits.length === 0 ? (
        <p className="empty">No neighbours match these filters.</p>
      ) : (
        <ol className={`nlist ${loading ? "is-stale" : ""}`}>
          {hits.map((h, i) => {
            const sibling = showLabels && clusterId !== null && h.cluster_id === clusterId;
            return (
              <li
                key={h.id}
                className={`${hovered === h.id ? "hl" : ""} ${sibling ? "sibling" : ""}`}
                onMouseEnter={() => onHover(h.id)}
                onMouseLeave={() => onHover(null)}
              >
                <span className="nrank">{sibling ? "✓" : i + 1}</span>
                <div className="nbody">
                  <Link to={fundPath(h.id)} className="fund-link">
                    {h.name}
                  </Link>
                  <span className="sub">
                    {h.ia_sector} · <Num value={h.ocf} digits={2} suffix="%" />
                  </span>
                  <span className="nfoot">
                    <Fingerprint vector={h.exposure_vector} layout={meta?.exposure_layout ?? null} />
                    {h.ranks && (
                      <span className="ranks" title="Rank in the text and exposure lists">
                        T{h.ranks.text ?? "–"} · E{h.ranks.exposure ?? "–"}
                      </span>
                    )}
                  </span>
                </div>
                <ScoreBar fill={scoreFill(h.score, mode)} label={score(h.score, mode)} />
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
