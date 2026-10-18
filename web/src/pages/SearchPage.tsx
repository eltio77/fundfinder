import { type FormEvent, useEffect, useState } from "react";

import { FilterBar, SettingsBar } from "../components/Controls";
import { ResultsTable } from "../components/ResultsTable";
import { ErrorNote, Skeleton } from "../components/ui";
import { api, type Filters, type SearchSettings } from "../lib/api";
import { ms } from "../lib/format";
import { useMeta, useRequest } from "../lib/hooks";
import { readQuery, writeQuery } from "../lib/params";
import { navigate } from "../lib/router";

const EXAMPLES = [
  "cheap S&P 500 tracker",
  "UK dividend income from quality companies",
  "gold and precious metals miners",
  "Japanese companies improving governance",
  "short-dated UK government bonds",
  "AI and semiconductor growth",
];

export function SearchPage({ params }: { params: URLSearchParams }) {
  const meta = useMeta();
  const { q, filters, settings } = readQuery(params);
  const [draft, setDraft] = useState(q);
  useEffect(() => setDraft(q), [q]);

  const go = (nextQ: string, f: Filters, s: SearchSettings, replace = false) =>
    navigate(`/${writeQuery(nextQ.trim(), f, s)}`, { replace });

  const key = q ? JSON.stringify([q, filters, settings]) : null;
  const { data, error, loading, retryIn, reload } = useRequest(key, (signal) =>
    api.search(q, filters, settings, signal),
  );

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (draft.trim()) go(draft, filters, settings);
  };

  return (
    <div className="page page-search">
      <section className={`hero-search ${q ? "compact" : ""}`}>
        <p className="kicker">Semantic search · {meta?.embed_model ?? "voyage-4"} · Atlas Vector Search</p>
        <h1 className="display">
          Find funds by <em>what they do</em>,<br />
          not what they're called.
        </h1>
        <form className="searchbox" onSubmit={submit} role="search">
          <label htmlFor="q" className="sr-only">
            Describe a fund
          </label>
          <input
            id="q"
            type="search"
            value={draft}
            autoFocus
            autoComplete="off"
            placeholder="Describe a fund: “low-cost global equity tracker”"
            onChange={(e) => setDraft(e.target.value)}
          />
          <button type="submit" disabled={!draft.trim()}>
            Search <span aria-hidden>→</span>
          </button>
        </form>
        {!q && (
          <div className="examples">
            <span className="muted">Try</span>
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" className="chip" onClick={() => go(ex, filters, settings)}>
                {ex}
              </button>
            ))}
          </div>
        )}
      </section>

      <div className="toolbar">
        <FilterBar filters={filters} meta={meta} onChange={(f) => go(q, f, settings, true)} />
        <SettingsBar settings={settings} meta={meta} onChange={(s) => go(q, filters, s, true)} />
      </div>

      {q && (
        <section className="results-section" aria-live="polite">
          <div className="results-head">
            <h2>
              <span className="muted">Results for</span> “{q}”
            </h2>
            {data && !loading && (
              <p className="mono muted">
                {data.results.length} funds · {ms(data.took_ms)} ·{" "}
                {data.exact ? "exact" : `numCandidates ${data.num_candidates}`}
              </p>
            )}
          </div>
          {error && (retryIn !== null || !loading) ? (
            <ErrorNote error={error} retryIn={retryIn} onRetry={reload} />
          ) : loading && !data ? (
            <Skeleton rows={8} />
          ) : data && data.results.length === 0 ? (
            <p className="empty">No funds match these filters.</p>
          ) : data ? (
            <div className={loading ? "is-stale" : ""}>
              <ResultsTable hits={data.results} mode="text" />
            </div>
          ) : null}
        </section>
      )}

      {!q && (
        <section className="modes">
          <article>
            <span className="mode-num mono">01</span>
            <h3>Text</h3>
            <p>
              Each fund's profile (objective, holdings, sector and region split) is embedded with{" "}
              <em>voyage-4</em> by Atlas Automated Embedding. Your query is embedded the same way.
            </p>
          </article>
          <article>
            <span className="mode-num mono">02</span>
            <h3>Exposure</h3>
            <p>
              A 26-dimension fingerprint of sector, region and asset-class weights. Funds that{" "}
              <em>hold</em> alike sit close together, whatever their names say.
            </p>
          </article>
          <article>
            <span className="mode-num mono">03</span>
            <h3>Fused</h3>
            <p>
              Reciprocal rank fusion of both lists. Open any fund to compare all three side by side.
            </p>
          </article>
        </section>
      )}
    </div>
  );
}
