import { type FormEvent, useEffect, useState } from "react";

import { SettingsFields } from "../components/Controls";
import { HowItWorksGuide } from "../components/HowItWorksGuide";
import { IconSearch } from "../components/Icons";
import { Methodology } from "../components/Methodology";
import { ResultList } from "../components/ResultList";
import { SimpleFilters } from "../components/SimpleFilters";
import { Understanding } from "../components/Understanding";
import { TestSets } from "../components/TestSets";
import { ErrorNote, Skeleton, Tabs, Toggle } from "../components/ui";
import { api, type Filters, type SearchSettings, type Sort, withAiFallback } from "../lib/api";
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
  { q: "low cost invests in Apple", tone: "coral" },
  { q: "highest exposure to NVIDIA", tone: "lilac" },
];

// Subtitle for the results order: "auto" when the server inferred it from the query.
const ORDER_NOTE: Record<Exclude<Sort, "auto">, { auto: string; chosen: string }> = {
  relevance: { auto: "Best matches first.", chosen: "Best matches first." },
  cost: {
    auto: "You asked for low cost, so the closest matches are shown cheapest first.",
    chosen: "Closest matches, cheapest first.",
  },
  cost_desc: {
    auto: "You asked for high cost, so the closest matches are shown most expensive first.",
    chosen: "Closest matches, most expensive first.",
  },
};

export function SearchPage({ params }: { params: URLSearchParams }) {
  const meta = useMeta();
  const expert = useExpert();
  const { q, sort, ignore, ai, filters, settings } = readQuery(params);
  const aiAvailable = meta?.llm_intent?.available ?? false;
  const [draft, setDraft] = useState(q);
  useEffect(() => setDraft(q), [q]);
  // The box is autofocused on load, so focus alone doesn't count as interacting.
  const [touched, setTouched] = useState(false);
  const [focused, setFocused] = useState(false);
  const engaged = touched && (focused || draft.trim() !== "");

  // A new query starts fresh (auto order, nothing ignored); filter, setting and
  // order changes keep the user's other choices. The AI mode carries over.
  const go = (
    nextQ: string,
    f: Filters,
    s: SearchSettings,
    replace = false,
    o: Sort = "auto",
    ig: string[] = [],
    withAi = ai,
  ) => navigate(`/${writeQuery(nextQ.trim(), f, s, o, ig, withAi)}`, { replace });
  // Switching mode re-reads the same query, so earlier chip removals no longer apply.
  const setAi = (on: boolean) => go(q, filters, settings, true, "auto", [], on);
  const refine = (changes: { f?: Filters; s?: SearchSettings; o?: Sort; ig?: string[] }) =>
    go(q, changes.f ?? filters, changes.s ?? settings, true, changes.o ?? sort, changes.ig ?? ignore);

  const key = q ? JSON.stringify([q, sort, ignore, ai, filters, settings]) : null;
  const { data, error, loading, retryIn, reload } = useRequest(key, (signal) =>
    withAiFallback(ai, (useAi) => api.search(q, sort, ignore, useAi, filters, settings, signal)),
  );
  const orderNote = data ? ORDER_NOTE[data.sort][sort === "auto" ? "auto" : "chosen"] : "";
  const clusters = useRequest(expert ? "clusters" : null, (signal) => api.clusters(signal));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (draft.trim()) go(draft, filters, settings);
  };

  return (
    <div className="stack">
      {/* The title stays; once you search or start typing it just gets smaller. */}
      <section className={`hero ${q ? "hero-compact hero-engaged" : engaged ? "hero-engaged" : ""}`}>
        <span className="pill pill-green">Plain-English fund search</span>
        <h1 className="hero-title">
          Find funds by <em>what they do</em>, not what they're called.
        </h1>
        <div className="hero-sub-wrap">
          <p className="hero-sub">
            Describe what you're looking for in your own words. Fund Finder reads every fund's
            description and holdings to find the closest matches.
          </p>
        </div>
        <form className="hero-search" onSubmit={submit} role="search">
          <IconSearch width={22} height={22} />
          <input
            type="search"
            value={draft}
            autoFocus={!q}
            autoComplete="off"
            aria-label="Describe a fund"
            placeholder="e.g. a low-cost fund that invests around the world"
            onChange={(e) => {
              setTouched(true);
              setDraft(e.target.value);
            }}
            onPointerDown={() => setTouched(true)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
          />
          <button type="submit" className="btn-dark" disabled={!draft.trim()}>
            Search
          </button>
        </form>
        <div className="search-mode">
          <Toggle
            checked={ai && aiAvailable}
            onChange={setAi}
            disabled={!aiAvailable}
            title={
              aiAvailable
                ? "An AI model reads what you mean: typos, vague wording and well-known names"
                : "Not available: the server has no AI key configured"
            }
          >
            Interpret with AI <span className="pill pill-amber">Beta</span>
          </Toggle>
          <span className="search-mode-hint">
            {ai && aiAvailable
              ? "Reads what you mean, e.g. “cheap well known UK” → cheap FTSE 100 trackers."
              : "Off: searches your words as written."}
          </span>
        </div>
        <div className="chips" role="group" aria-label="Example searches">
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
                {orderNote} Open a fund to see others like it.
                {expert && data && !loading && (
                  <span className="mono">
                    {" "}
                    · {ms(data.took_ms)} · {data.exact ? "exact" : `nc ${data.num_candidates}`}
                  </span>
                )}
              </p>
            </div>
            {data && (
              <Tabs<Exclude<Sort, "auto">>
                value={data.sort}
                label="Order results by"
                options={[
                  { value: "relevance", label: "Best match" },
                  { value: "cost", label: "Lowest cost" },
                  { value: "cost_desc", label: "Highest cost" },
                ]}
                onChange={(o) => refine({ o })}
              />
            )}
          </header>
          {data?.interpretation && (
            <Understanding
              q={q}
              interpretation={data.interpretation}
              ignored={ignore}
              onIgnore={(k) => refine({ ig: [...ignore, k] })}
              onReset={() => refine({ ig: [] })}
            />
          )}
          <SimpleFilters filters={filters} meta={meta} onChange={(f) => refine({ f })} />
          {expert && (
            <div className="expert-bar">
              <SettingsFields settings={settings} meta={meta} onChange={(s) => refine({ s })} />
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
      >
        <HowItWorksGuide />
      </Methodology>

      {expert && !q && <TestSets clusters={clusters.data} />}
    </div>
  );
}
