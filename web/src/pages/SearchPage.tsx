import { type FormEvent, useEffect, useState } from "react";

import { FilterFields, ManagementTabs, SettingsFields } from "../components/Controls";
import { IconArrowUpRight, IconInfo, IconSearch, IconSparkle } from "../components/Icons";
import { ResultsTable } from "../components/ResultsTable";
import { ErrorNote, FadeText, Num, Skeleton, Stat } from "../components/ui";
import { api, type Filters, type SearchResponse, type SearchSettings } from "../lib/api";
import { ms } from "../lib/format";
import { useMeta, useRequest } from "../lib/hooks";
import { readQuery, writeQuery } from "../lib/params";
import { navigate } from "../lib/router";

const EXAMPLES = [
  { q: "cheap S&P 500 tracker", tone: "forest" },
  { q: "UK dividend income from quality companies", tone: "amber" },
  { q: "gold and precious metals miners", tone: "coral" },
  { q: "Japanese companies improving governance", tone: "lilac" },
  { q: "short-dated UK government bonds", tone: "forest" },
  { q: "AI and semiconductor growth", tone: "amber" },
];

const MODES = [
  {
    tone: "forest",
    title: "Text",
    figure: "1024",
    unit: "dims",
    body: "Fund profiles embedded with voyage-4 by Atlas Automated Embedding.",
  },
  {
    tone: "cream",
    title: "Exposure",
    figure: "26",
    unit: "dims",
    body: "Sector, region and asset-class weights compared by cosine.",
  },
  {
    tone: "lilac",
    title: "Fused",
    figure: "k=60",
    unit: "RRF",
    body: "Reciprocal rank fusion of both lists. Open a fund to compare.",
  },
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

  const examples = (
    <div className="examples">
      {EXAMPLES.map((ex) => (
        <button
          key={ex.q}
          type="button"
          className={`example ${ex.q === q ? "active" : ""}`}
          onClick={() => go(ex.q, filters, settings)}
        >
          <span className={`dot sw-${ex.tone}`} />
          <span className="example-q">{ex.q}</span>
          <IconArrowUpRight width={16} height={16} />
        </button>
      ))}
    </div>
  );

  return (
    <div className="stack">
      <div className="grid">
        <div className="col-main">
          <section className="lead">
            <span className="lead-label">Describe a fund</span>
            <form className="bigsearch" onSubmit={submit} role="search">
              <input
                type="search"
                value={draft}
                autoFocus={!q}
                autoComplete="off"
                aria-label="Describe a fund"
                placeholder="low-cost global equity tracker"
                onChange={(e) => setDraft(e.target.value)}
              />
              <button type="submit" className="btn-dark" disabled={!draft.trim()}>
                <IconSearch width={16} height={16} />
                Search
              </button>
            </form>
            <p className="lead-foot">
              Semantic search over <b>300</b> synthetic UK funds · embedded with{" "}
              <b>{meta?.embed_model ?? "voyage-4"}</b>
            </p>
          </section>

          {q ? (
            data && !loading ? (
              <StatRow data={data} />
            ) : null
          ) : (
            <section className="card">
              <header className="card-head">
                <h3>
                  Three ways to measure similarity{" "}
                  <span className="hint">
                    <IconInfo width={15} height={15} />
                  </span>
                </h3>
              </header>
              <div className="mix mix-modes">
                {MODES.map((m) => (
                  <div className="mix-item" key={m.title}>
                    <span className={`dot sw-${m.tone}`} />
                    <span className="mix-val">
                      {m.figure} <span className="faded">{m.unit}</span>
                    </span>
                    <span className="mix-name">{m.title}</span>
                    <span className={`mix-block sw-${m.tone}`} />
                    <p className="mix-body">{m.body}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {q && (
            <div className="chips" aria-label="Example queries">
              {EXAMPLES.filter((ex) => ex.q !== q).map((ex) => (
                <button key={ex.q} type="button" className="chip" onClick={() => go(ex.q, filters, settings)}>
                  <span className={`dot sw-${ex.tone}`} />
                  {ex.q}
                </button>
              ))}
            </div>
          )}
        </div>

        <aside className="col-side">
          {q ? (
            data && !loading && data.results.length > 1 ? (
              <InsightCard data={data} />
            ) : (
              <section className="card">
                <Skeleton rows={4} />
              </section>
            )
          ) : (
            <section className="card">
              <header className="card-head">
                <h3>Try a query</h3>
              </header>
              {examples}
            </section>
          )}
        </aside>
      </div>

      {q && (
        <section className="card">
          <header className="card-head">
            <div>
              <h3>Results</h3>
              <p className="card-head-sub">for “{q}”</p>
            </div>
            <ManagementTabs filters={filters} onChange={(f) => go(q, f, settings, true)} />
          </header>
          <div className="toolbar">
            <FilterFields filters={filters} meta={meta} onChange={(f) => go(q, f, settings, true)} />
            <SettingsFields settings={settings} meta={meta} onChange={(s) => go(q, filters, s, true)} />
          </div>
          <div aria-live="polite">
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
          </div>
        </section>
      )}
    </div>
  );
}

function StatRow({ data }: { data: SearchResponse }) {
  const top = data.results[0]?.score ?? 0;
  return (
    <div className="stats">
      <Stat
        label="Results"
        value={data.results.length}
        foot={`of ${data.limit} requested`}
        trend={Object.keys(data.filters).length ? `${Object.keys(data.filters).length} filters` : null}
      />
      <Stat
        label="Latency"
        value={ms(data.took_ms)}
        foot={data.exact ? "Exact (ENN)" : "ANN"}
        trend={data.exact ? "full scan" : `nc ${data.num_candidates}`}
      />
      <Stat
        label="Best score"
        value={<Num value={top} digits={3} fade={2} />}
        foot="Atlas score"
        trend="0.5 = unrelated"
      />
    </div>
  );
}

/** Reads the score distribution: a tight spread means the query doesn't discriminate. */
function InsightCard({ data }: { data: SearchResponse }) {
  const hits = data.results;
  const top = hits[0];
  const spread = hits[0].score - hits[hits.length - 1].score;
  const gap = hits[0].score - hits[1].score;
  const sectors = new Set(hits.map((h) => h.ia_sector)).size;
  return (
    <section className="card">
      <header className="insight-head">
        <span className="spark">
          <IconSparkle />
        </span>
        <div>
          <h3>Search insight</h3>
          <p className="muted small">Read from the score distribution</p>
        </div>
      </header>
      <div className="insights">
        <div className="insight">
          <span className="insight-label">Top match</span>
          <FadeText
            strong={top.name}
            soft={
              gap > 0.01
                ? `leads clearly by ${gap.toFixed(3)}`
                : gap < 0.001
                  ? "is level with the next fund"
                  : `is barely ahead, by ${gap.toFixed(3)}`
            }
          />
        </div>
        <div className="insight">
          <span className="insight-label">Spread</span>
          <FadeText
            strong={spread < 0.02 ? "Tightly bunched" : "Well separated"}
            soft={`${spread.toFixed(3)} across ${hits.length} funds in ${sectors} sector${sectors === 1 ? "" : "s"}`}
          />
        </div>
      </div>
    </section>
  );
}
