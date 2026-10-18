import { type CSSProperties, useState } from "react";

import { SettingsBar } from "../components/Controls";
import { Fingerprint } from "../components/Fingerprint";
import { SimilarColumn } from "../components/SimilarColumn";
import { ErrorNote, Link, Skeleton, Toggle } from "../components/ui";
import { WeightList } from "../components/WeightList";
import { api, type Filters, type Fund, type Mode, type SearchSettings } from "../lib/api";
import { clusterLabel, ocf } from "../lib/format";
import { useMeta, usePersistentFlag, useRequest } from "../lib/hooks";
import { DEFAULT_LIMIT } from "../lib/params";

const MODES: Mode[] = ["text", "exposure", "both"];

export function FundPage({ id }: { id: string }) {
  const fund = useRequest(id, (signal) => api.fund(id, signal));

  if (fund.error) {
    return (
      <div className="page">
        <ErrorNote error={fund.error} retryIn={fund.retryIn} onRetry={fund.reload} />
        <Link to="/" className="btn-link">
          ← Back to search
        </Link>
      </div>
    );
  }
  if (!fund.data || fund.data.id !== id) {
    return (
      <div className="page">
        <Skeleton rows={10} />
      </div>
    );
  }
  return <FundView fund={fund.data} />;
}

function FundView({ fund }: { fund: Fund }) {
  const meta = useMeta();
  const [settings, setSettings] = useState<SearchSettings>({
    limit: DEFAULT_LIMIT,
    numCandidates: null,
    exact: false,
  });
  const [cheaperOnly, setCheaperOnly] = useState(false);
  const [showLabels, setShowLabels] = usePersistentFlag("ff.showLabels", true);
  const [hovered, setHovered] = useState<string | null>(null);

  const filters: Filters = cheaperOnly ? { ocf_max: Math.max(0, fund.ocf - 0.01) } : {};
  const key = JSON.stringify([fund.id, settings, filters]);
  const text = useRequest(`text:${key}`, (s) => api.similar(fund.id, "text", filters, settings, s));
  const exposure = useRequest(`exposure:${key}`, (s) =>
    api.similar(fund.id, "exposure", filters, settings, s),
  );
  const both = useRequest(`both:${key}`, (s) => api.similar(fund.id, "both", filters, settings, s));
  const states = { text, exposure, both };

  return (
    <div className="page page-fund">
      <nav className="crumbs">
        <Link to="/">Search</Link> <span aria-hidden>/</span>{" "}
        <span className="mono">{fund.id}</span>
      </nav>

      <section className="fund-hero">
        <div className="fund-title">
          <p className="kicker">
            {fund.ia_sector} · {fund.asset_class}
          </p>
          <h1 className="display">{fund.name}</h1>
          <p className="provider">
            {fund.provider} · {fund.is_passive ? "Passive" : "Active"}
          </p>
          <blockquote>{fund.objective}</blockquote>
        </div>
        <aside className="ledger">
          <dl>
            <div>
              <dt>OCF</dt>
              <dd className="mono big">{ocf(fund.ocf)}</dd>
            </div>
            <div>
              <dt>Tracks</dt>
              <dd>{fund.tracked_index ?? "Not an index fund"}</dd>
            </div>
            {showLabels && fund.cluster_id && (
              <div>
                <dt>Test label</dt>
                <dd className="mono">{clusterLabel(fund.cluster_id)}</dd>
              </div>
            )}
          </dl>
          <div className="ledger-fp">
            <span className="label">Exposure fingerprint</span>
            <Fingerprint vector={fund.exposure_vector} layout={meta?.exposure_layout ?? null} size="lg" />
          </div>
        </aside>
      </section>

      <section className="composition">
        <WeightList title="Top holdings" weights={fund.top_holdings} />
        <WeightList title="Sectors" weights={fund.sector_weights} limit={8} />
        <WeightList title="Regions" weights={fund.region_weights} tone="accent" />
        <WeightList title="Asset classes" weights={fund.asset_class_weights} tone="sage" />
      </section>

      <section className="neighbours-section">
        <div className="section-head">
          <h2 className="display-sm">
            Nearest <em>neighbours</em>
          </h2>
          <div className="section-tools">
            <SettingsBar settings={settings} meta={meta} onChange={setSettings} />
            <div className="toggles">
              <Toggle checked={cheaperOnly} onChange={setCheaperOnly}>
                Only cheaper than {ocf(fund.ocf)}
              </Toggle>
              <Toggle checked={showLabels} onChange={setShowLabels}>
                Show test labels
              </Toggle>
            </div>
          </div>
        </div>
        <div className="columns">
          {MODES.map((m, i) => (
            <div key={m} className="col-wrap" style={{ "--i": i } as CSSProperties}>
              <SimilarColumn
                mode={m}
                state={states[m]}
                clusterId={fund.cluster_id}
                showLabels={showLabels}
                hovered={hovered}
                onHover={setHovered}
              />
            </div>
          ))}
        </div>
        <p className="footnote">
          Hover a fund to find it in the other columns. Text and fused results each cost one Voyage
          embedding call; exposure uses the stored vector.
        </p>
      </section>
    </div>
  );
}
