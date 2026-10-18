import { type FormEvent, useEffect, useState } from "react";

import { SettingsFields } from "../components/Controls";
import { IconSearch } from "../components/Icons";
import { Methodology } from "../components/Methodology";
import { ResultList } from "../components/ResultList";
import { SimpleFilters } from "../components/SimpleFilters";
import { TestSets } from "../components/TestSets";
import { ErrorNote, Skeleton } from "../components/ui";
import { api, type Filters, type SearchSettings } from "../lib/api";
import { ms } from "../lib/format";
import { useExpert, useMeta, useRequest } from "../lib/hooks";
import { readQuery, writeQuery } from "../lib/params";
import { navigate } from "../lib/router";

const EXAMPLES = [
  { q: "a cheap fund that follows the US stock market", tone: "forest" },
  { q: "steady income from big UK companies", tone: "amber" },
  { q: "gold mining shares", tone: "coral" },
  { q: "Japanese companies that are reforming", tone: "lilac" },
  { q: "low-risk UK government bonds", tone: "forest" },
  { q: "artificial intelligence and chips", tone: "amber" },
];

export function SearchPage({ params }: { params: URLSearchParams }) {
  const meta = useMeta();
  const expert = useExpert();
  const { q, filters, settings } = readQuery(params);
  const [draft, setDraft] = useState(q);
  useEffect(() => setDraft(q), [q]);

  const go = (nextQ: string, f: Filters, s: SearchSettings, replace = false) =>
    navigate(`/${writeQuery(nextQ.trim(), f, s)}`, { replace });

  const key = q ? JSON.stringify([q, filters, settings]) : null;
  const { data, error, loading, retryIn, reload } = useRequest(key, (signal) =>
    api.search(q, filters, settings, signal),
  );
  const clusters = useRequest(expert ? "clusters" : null, (signal) => api.clusters(signal));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (draft.trim()) go(draft, filters, settings);
  };

  return (
    <div className="stack">
      <section className={`hero ${q ? "hero-compact" : ""}`}>
        {!q && (
          <>
            <span className="pill pill-green">Plain-English fund search</span>
            <h1 className="hero-title">
              Find funds by <em>what they do</em>, not what they're called.
            </h1>
            <p className="hero-sub">
              Describe what you're looking for in your own words. Fund Finder reads every fund's
              description and holdings to find the closest matches.
            </p>
          </>
        )}
        <form className="hero-search" onSubmit={submit} role="search">
          <IconSearch width={22} height={22} />
          <input
            type="search"
            value={draft}
            autoFocus={!q}
            autoComplete="off"
            aria-label="Describe a fund"
            placeholder="e.g. a low-cost fund that invests around the world"
            onChange={(e) => setDraft(e.target.value)}
          />
          <button type="submit" className="btn-dark" disabled={!draft.trim()}>
            Search
          </button>
        </form>
        <div className="chips" aria-label="Example searches">
          <span className="chips-label">Try</span>
          {EXAMPLES.filter((ex) => ex.q !== q).map((ex) => (
            <button key={ex.q} type="button" className="chip" onClick={() => go(ex.q, filters, settings)}>
              <span className={`dot sw-${ex.tone}`} />
              {ex.q}
            </button>
          ))}
        </div>
      </section>

      {q && (
        <section className="card">
          <header className="results-head">
            <div>
              <h2>
                {data && !loading ? `${data.results.length} funds match` : "Searching…"}{" "}
                <span className="muted">“{q}”</span>
              </h2>
              <p className="card-head-sub">
                Best matches first. Open a fund to see others like it.
                {expert && data && !loading && (
                  <span className="mono">
                    {" "}
                    · {ms(data.took_ms)} · {data.exact ? "exact" : `nc ${data.num_candidates}`}
                  </span>
                )}
              </p>
            </div>
          </header>
          <SimpleFilters filters={filters} meta={meta} onChange={(f) => go(q, f, settings, true)} />
          {expert && (
            <div className="expert-bar">
              <SettingsFields settings={settings} meta={meta} onChange={(s) => go(q, filters, s, true)} />
            </div>
          )}
          <div aria-live="polite">
            {error && (retryIn !== null || !loading) ? (
              <ErrorNote error={error} retryIn={retryIn} onRetry={reload} />
            ) : loading && !data ? (
              <Skeleton rows={6} />
            ) : data && data.results.length === 0 ? (
              <p className="empty">No funds match these filters. Try removing one.</p>
            ) : data ? (
              <div className={loading ? "is-stale" : ""}>
                <ResultList hits={data.results} />
              </div>
            ) : null}
          </div>
        </section>
      )}

      <Methodology
        lead={
          q
            ? undefined
            : "Every result is found in up to three ways. Open any fund to see the funds most like it."
        }
      />

      {expert && !q && <TestSets clusters={clusters.data} />}
    </div>
  );
}
