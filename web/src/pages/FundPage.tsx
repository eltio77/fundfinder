import { useEffect, useState } from "react";

import { SettingsFields } from "../components/Controls";
import { ExposureCard } from "../components/ExposureCard";
import { Fingerprint } from "../components/Fingerprint";
import { Gauge } from "../components/Gauge";
import { HoldingsTable } from "../components/HoldingsTable";
import { IconSparkle } from "../components/Icons";
import { SimilarColumn } from "../components/SimilarColumn";
import { ErrorNote, FadeText, Link, Num, Skeleton, Stat, Toggle } from "../components/ui";
import { api, type Filters, type Fund, type Mode, type SearchSettings } from "../lib/api";
import { clusterLabel, clusterSize, siblingStats } from "../lib/format";
import { rememberFund, useMeta, usePersistentFlag, useRequest } from "../lib/hooks";
import { DEFAULT_LIMIT } from "../lib/params";

const MODES: Mode[] = ["text", "exposure", "both"];

export function FundPage({ id }: { id: string }) {
  const fund = useRequest(id, (signal) => api.fund(id, signal));

  useEffect(() => {
    if (fund.data?.id === id) rememberFund(fund.data);
  }, [fund.data, id]);

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
        <Skeleton rows={10} />
      </div>
    );
  }
  return <FundView fund={fund.data} />;
}

function firstSentence(text: string): [string, string] {
  const i = text.indexOf(". ");
  return i === -1 ? [text, ""] : [text.slice(0, i + 1), text.slice(i + 2)];
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

  // Agreement: share of the top-N that text and exposure have in common.
  const textIds = new Set(text.data?.results.map((h) => h.id) ?? []);
  const shared = exposure.data?.results.filter((h) => textIds.has(h.id)).length ?? 0;
  const n = Math.max(text.data?.results.length ?? 0, exposure.data?.results.length ?? 0);
  const agreement = n ? shared / n : 0;
  const fusedSiblings = siblingStats(fund.cluster_id, clusterSize(fund.cluster_id), both.data?.results ?? []);
  const [objLead, objRest] = firstSentence(fund.objective);

  return (
    <div className="stack">
      <div className="grid">
        <div className="col-main">
          <section className="lead">
            <span className="lead-label">
              {fund.provider} · {fund.ia_sector}
            </span>
            <h2 className="lead-title">{fund.name}</h2>
            <p className="lead-foot">
              {fund.is_passive ? (
                <>
                  Tracks the <b>{fund.tracked_index}</b>
                </>
              ) : (
                <>Actively managed {fund.asset_class.toLowerCase()} fund</>
              )}
            </p>
          </section>

          <div className="stats">
            <Stat
              label="Ongoing charge"
              value={<Num value={fund.ocf} digits={2} suffix="%" />}
              foot="OCF per year"
              trend={fund.ocf < 0.3 ? "Low cost" : fund.ocf > 0.9 ? "High cost" : null}
            />
            <Stat
              label="Management"
              value={fund.is_passive ? "Passive" : "Active"}
              foot={fund.asset_class}
              trend={`${fund.top_holdings.length} top holdings`}
            />
            <Stat
              label="Test label"
              value={fund.cluster_id ? clusterLabel(fund.cluster_id)!.split(" · ")[0] : "Background"}
              foot={fund.cluster_id ? clusterLabel(fund.cluster_id)!.split(" · ")[1] : "No designed neighbours"}
              trend={fund.cluster_id && clusterSize(fund.cluster_id) > 1 ? `${clusterSize(fund.cluster_id) - 1} siblings` : null}
            />
          </div>

          <ExposureCard fund={fund} />
          <HoldingsTable holdings={fund.top_holdings} />
        </div>

        <aside className="col-side">
          <section className="card">
            <header className="insight-head">
              <span className="spark">
                <IconSparkle />
              </span>
              <div>
                <h3>Fund objective</h3>
                <p className="muted small">Part of the embedded profile</p>
              </div>
            </header>
            <div className="insights insights-1">
              <div className="insight">
                <span className="insight-label">In its own words</span>
                <FadeText strong={objLead} soft={objRest} />
              </div>
              <div className="insight">
                <span className="insight-label">Exposure fingerprint</span>
                <Fingerprint vector={fund.exposure_vector} layout={meta?.exposure_layout ?? null} size="lg" />
              </div>
            </div>
          </section>

          <section className="card">
            <header className="card-head">
              <h3>Mode agreement</h3>
            </header>
            <span className={`pill ${agreement >= 0.5 ? "pill-green" : agreement >= 0.25 ? "pill-amber" : "pill-coral"}`}>
              {!n ? "Waiting for results" : agreement >= 0.5 ? "Aligned" : agreement >= 0.25 ? "Partly aligned" : "Diverging"}
            </span>
            <div className="gauge-row">
              <div className="gauge-copy">
                <span className="gauge-big">
                  {shared}
                  <span className="faded">/{n || "–"}</span>
                </span>
                <p className="small muted">
                  neighbours appear in both the text and the exposure top {n || settings.limit}.
                </p>
                {showLabels && fusedSiblings && (
                  <p className="small">
                    Fused found{" "}
                    <b className={fusedSiblings.found === fusedSiblings.total ? "pos" : ""}>
                      {fusedSiblings.found}/{fusedSiblings.total}
                    </b>{" "}
                    designed siblings.
                  </p>
                )}
              </div>
              <Gauge value={agreement} label="Mode agreement" caption="overlap" />
            </div>
          </section>
        </aside>
      </div>

      <section className="card">
        <header className="card-head card-head-wrap">
          <div>
            <h3>Nearest neighbours</h3>
            <p className="muted small">Hover a fund to find it in the other columns.</p>
          </div>
          <div className="neighbour-tools">
            <SettingsFields settings={settings} meta={meta} onChange={setSettings} />
            <div className="toggles">
              <Toggle checked={cheaperOnly} onChange={setCheaperOnly}>
                Only cheaper
              </Toggle>
              <Toggle checked={showLabels} onChange={setShowLabels}>
                Test labels
              </Toggle>
            </div>
          </div>
        </header>
        <div className="columns">
          {MODES.map((m) => (
            <SimilarColumn
              key={m}
              mode={m}
              state={states[m]}
              clusterId={fund.cluster_id}
              showLabels={showLabels}
              hovered={hovered}
              onHover={setHovered}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
