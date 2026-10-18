import { useState } from "react";

import { SettingsFields } from "../components/Controls";
import { ExposureCard } from "../components/ExposureCard";
import { Fingerprint } from "../components/Fingerprint";
import { Gauge } from "../components/Gauge";
import { HoldingsTable } from "../components/HoldingsTable";
import { Methodology } from "../components/Methodology";
import { ResultList } from "../components/ResultList";
import { SimilarColumn } from "../components/SimilarColumn";
import { ErrorNote, FadeText, Link, Num, Skeleton, Toggle } from "../components/ui";
import { api, type Filters, type Fund, type Mode, type SearchSettings } from "../lib/api";
import { clusterLabel, clusterSize, matchReason, siblingStats } from "../lib/format";
import { useExpert, useMeta, useRequest } from "../lib/hooks";
import { DEFAULT_LIMIT } from "../lib/params";
import { navigate } from "../lib/router";

const MODES: Mode[] = ["text", "exposure", "both"];

export function FundPage({ id }: { id: string }) {
  const fund = useRequest(id, (signal) => api.fund(id, signal));

  if (fund.error) {
    return (
      <div className="card">
        <ErrorNote error={fund.error} retryIn={fund.retryIn} onRetry={fund.reload} />
        <Link to="/" className="btn-ghost">
          Back to search
        </Link>
      </div>
    );
  }
  if (!fund.data || fund.data.id !== id) {
    return (
      <div className="card">
        <Skeleton rows={8} />
      </div>
    );
  }
  return <FundView fund={fund.data} />;
}

function firstSentence(text: string): [string, string] {
  const i = text.indexOf(". ");
  return i === -1 ? [text, ""] : [text.slice(0, i + 1), text.slice(i + 2)];
}

function back() {
  // Return to the results the user came from when there are any.
  if (window.history.length > 1 && document.referrer.startsWith(window.location.origin)) {
    window.history.back();
  } else {
    navigate("/");
  }
}

function FundView({ fund }: { fund: Fund }) {
  const meta = useMeta();
  const expert = useExpert();
  const [settings, setSettings] = useState<SearchSettings>({
    limit: DEFAULT_LIMIT,
    numCandidates: null,
    exact: false,
  });
  const [cheaperOnly, setCheaperOnly] = useState(false);
  const [compare, setCompare] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);

  const filters: Filters = cheaperOnly ? { ocf_max: Math.max(0, fund.ocf - 0.01) } : {};
  const key = JSON.stringify([fund.id, settings, filters]);
  // The fused list is the default view: one Voyage call, and its ranks say why each fund matched.
  const both = useRequest(`both:${key}`, (s) => api.similar(fund.id, "both", filters, settings, s));
  const showCompare = expert && compare;
  const text = useRequest(showCompare ? `text:${key}` : null, (s) =>
    api.similar(fund.id, "text", filters, settings, s),
  );
  const exposure = useRequest(showCompare ? `exposure:${key}` : null, (s) =>
    api.similar(fund.id, "exposure", filters, settings, s),
  );
  const states = { text, exposure, both };

  const hits = both.data?.results ?? [];
  const inBoth = hits.filter((h) => matchReason(h.ranks, hits.length).both).length;
  const agreement = hits.length ? inBoth / hits.length : 0;
  const siblings = siblingStats(fund.cluster_id, clusterSize(fund.cluster_id), hits);
  const [objLead, objRest] = firstSentence(fund.objective);

  return (
    <div className="stack">
      <button type="button" className="back" onClick={back}>
        ← Back
      </button>

      <section className="fund-hero">
        <span className="lead-label">
          {fund.provider} · {fund.ia_sector}
        </span>
        <h1 className="fund-title">{fund.name}</h1>
        <div className="facts">
          <span className="fact">
            <span className="fact-label">Annual cost</span>
            <span className="fact-value">
              <Num value={fund.ocf} digits={2} suffix="%" />
            </span>
          </span>
          <span className="fact">
            <span className="fact-label">Type</span>
            <span className="fact-value">{fund.is_passive ? "Index fund" : "Actively managed"}</span>
          </span>
          <span className="fact">
            <span className="fact-label">{fund.is_passive ? "Follows" : "Invests in"}</span>
            <span className="fact-value">
              {fund.is_passive ? fund.tracked_index?.replace(/ Index$/, "") : fund.asset_class}
            </span>
          </span>
          {expert && (
            <span className="fact">
              <span className="fact-label">Test label</span>
              <span className="fact-value small">{clusterLabel(fund.cluster_id) ?? "Background"}</span>
            </span>
          )}
        </div>
        <div className="objective">
          <span className="fact-label">What the fund says it does</span>
          <FadeText strong={objLead} soft={objRest} />
        </div>
        {expert && (
          <div className="objective">
            <span className="fact-label">Exposure fingerprint</span>
            <Fingerprint vector={fund.exposure_vector} layout={meta?.exposure_layout ?? null} size="lg" />
          </div>
        )}
      </section>

      <div className="grid-2">
        <ExposureCard fund={fund} />
        <HoldingsTable holdings={fund.top_holdings} />
      </div>

      <section className="card">
        <header className="results-head">
          <div>
            <h2>Funds like this</h2>
            <p className="card-head-sub">Closest matches on description and holdings combined.</p>
          </div>
          <Toggle checked={cheaperOnly} onChange={setCheaperOnly}>
            Only cheaper than <Num value={fund.ocf} digits={2} suffix="%" />
          </Toggle>
        </header>
        {expert && (
          <div className="expert-bar">
            <SettingsFields settings={settings} meta={meta} onChange={setSettings} />
          </div>
        )}
        {both.error && (both.retryIn !== null || !both.loading) ? (
          <ErrorNote error={both.error} retryIn={both.retryIn} onRetry={both.reload} />
        ) : both.loading && !both.data ? (
          <Skeleton rows={6} />
        ) : hits.length === 0 ? (
          <p className="empty">No similar funds{cheaperOnly ? " are cheaper than this one" : ""}.</p>
        ) : (
          <div className={both.loading ? "is-stale" : ""}>
            <ResultList hits={hits} fused clusterId={fund.cluster_id} />
          </div>
        )}
      </section>

      <Methodology
        title="How we found these"
        lead={
          hits.length > 0 ? (
            <>
              <b>
                {inBoth} of these {hits.length}
              </b>{" "}
              funds are in the top {hits.length} for both similar descriptions <i>and</i> similar
              holdings. The rest ranked highly on one of them.
              {expert && siblings && (
                <>
                  {" "}
                  Found{" "}
                  <b className={siblings.found === siblings.total ? "pos" : ""}>
                    {siblings.found}/{siblings.total}
                  </b>{" "}
                  designed siblings.
                </>
              )}
            </>
          ) : undefined
        }
        aside={
          hits.length > 0 ? (
            <div className="method-gauge">
              <Gauge value={agreement} label="Found by both methods" caption="found by both" />
            </div>
          ) : undefined
        }
      />

      {expert && (
        <section className="card">
          <header className="results-head">
            <div>
              <h2>Compare the methods</h2>
              <p className="card-head-sub">
                Each method's own list, side by side. Hover a fund to find it in the other columns.
              </p>
            </div>
            <Toggle checked={compare} onChange={setCompare}>
              Show side by side
            </Toggle>
          </header>
          {showCompare && (
            <div className="columns">
              {MODES.map((m) => (
                <SimilarColumn
                  key={m}
                  mode={m}
                  state={states[m]}
                  clusterId={fund.cluster_id}
                  showLabels
                  hovered={hovered}
                  onHover={setHovered}
                />
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
