import { useState } from "react";

import type { Fund } from "../lib/api";
import { pct } from "../lib/format";
import { IconInfo } from "./Icons";
import { Tabs } from "./ui";

type Tab = "sectors" | "regions" | "assets";

const TABS: { value: Tab; label: string }[] = [
  { value: "sectors", label: "Sectors" },
  { value: "regions", label: "Regions" },
  { value: "assets", label: "Asset types" },
];

const SWATCHES = ["forest", "cream", "lilac"] as const;

/** Top three weights of the chosen breakdown as proportional colour blocks. */
export function ExposureCard({ fund }: { fund: Fund }) {
  // Bond and cash funds have no sector exposure, so open on the first non-empty breakdown.
  const hasSectors = Object.values(fund.sector_weights).some((w) => w > 0);
  const [tab, setTab] = useState<Tab>(hasSectors ? "sectors" : "regions");
  const source =
    tab === "sectors"
      ? fund.sector_weights
      : tab === "regions"
        ? fund.region_weights
        : fund.asset_class_weights;
  const ranked = Object.entries(source)
    .filter(([, w]) => w > 0)
    .sort((a, b) => b[1] - a[1]);
  const top = ranked.slice(0, 3);
  const other = ranked.slice(3).reduce((s, [, w]) => s + w, 0);
  const topSum = top.reduce((s, [, w]) => s + w, 0) || 1;

  return (
    <section className="card">
      <header className="card-head">
        <div>
          <h3>
            What it invests in{" "}
            <span className="hint" title="Share of the whole fund">
              <IconInfo width={15} height={15} />
            </span>
          </h3>
          <p className="card-head-sub">Its three biggest areas</p>
        </div>
        <Tabs value={tab} options={TABS} onChange={setTab} label="Breakdown" />
      </header>
      {top.length === 0 ? (
        <p className="empty">Not applicable: this fund doesn't hold company shares.</p>
      ) : (
        <div className="mix">
          {top.map(([name, w], i) => (
            <div className="mix-item" key={name} style={{ flexGrow: Math.max(w / topSum, 0.18) }}>
              <span className={`dot sw-${SWATCHES[i]}`} />
              <span className="mix-val">{pct(w)}</span>
              <span className="mix-name">{name}</span>
              <span className={`mix-block sw-${SWATCHES[i]}`} />
            </div>
          ))}
        </div>
      )}
      {other > 0.001 && (
        <p className="mix-other">
          Everything else: {pct(other)}
        </p>
      )}
    </section>
  );
}
