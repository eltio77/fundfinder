import type { Filters, Meta, SearchSettings } from "../lib/api";
import { Tabs } from "./ui";

const LIMITS = [5, 10, 20, 50];

type Mgmt = "any" | "passive" | "active";
const MGMT: { value: Mgmt; label: string }[] = [
  { value: "any", label: "All" },
  { value: "passive", label: "Passive" },
  { value: "active", label: "Active" },
];

export function ManagementTabs({
  filters,
  onChange,
}: {
  filters: Filters;
  onChange: (f: Filters) => void;
}) {
  const value: Mgmt = filters.is_passive === undefined ? "any" : filters.is_passive ? "passive" : "active";
  return (
    <Tabs
      value={value}
      options={MGMT}
      label="Management"
      onChange={(v) => onChange({ ...filters, is_passive: v === "any" ? undefined : v === "passive" })}
    />
  );
}

export function FilterFields({
  filters,
  onChange,
  meta,
}: {
  filters: Filters;
  onChange: (f: Filters) => void;
  meta: Meta | null;
}) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  const active =
    filters.asset_class !== undefined || filters.ia_sector !== undefined || filters.ocf_max !== undefined;
  return (
    <div className="fields">
      <label className="field">
        <span>Asset class</span>
        <select
          value={filters.asset_class ?? ""}
          onChange={(e) => set({ asset_class: e.target.value || undefined })}
        >
          <option value="">All asset classes</option>
          {meta?.asset_classes.map((a) => <option key={a}>{a}</option>)}
        </select>
      </label>
      <label className="field field-wide">
        <span>IA sector</span>
        <select
          value={filters.ia_sector ?? ""}
          onChange={(e) => set({ ia_sector: e.target.value || undefined })}
        >
          <option value="">All sectors</option>
          {meta?.ia_sectors.map((s) => <option key={s}>{s}</option>)}
        </select>
      </label>
      <label className="field field-narrow">
        <span>Max OCF %</span>
        <input
          type="number"
          inputMode="decimal"
          min={0}
          step={0.05}
          placeholder="Any"
          value={filters.ocf_max ?? ""}
          onChange={(e) =>
            set({ ocf_max: e.target.value === "" ? undefined : Math.max(0, Number(e.target.value)) })
          }
        />
      </label>
      {active && (
        <button
          type="button"
          className="btn-ghost clear"
          onClick={() => onChange({ is_passive: filters.is_passive })}
        >
          Clear filters
        </button>
      )}
    </div>
  );
}

export function SettingsFields({
  settings,
  onChange,
  meta,
}: {
  settings: SearchSettings;
  onChange: (s: SearchSettings) => void;
  meta: Meta | null;
}) {
  const perResult = meta?.defaults.candidates_per_result ?? 20;
  return (
    <div className="fields">
      <label className="field field-narrow">
        <span>Limit</span>
        <select
          value={settings.limit}
          onChange={(e) => onChange({ ...settings, limit: Number(e.target.value) })}
        >
          {LIMITS.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </label>
      <label className={`field field-narrow ${settings.exact ? "is-disabled" : ""}`}>
        <span>numCandidates</span>
        <input
          type="number"
          min={settings.limit}
          max={meta?.defaults.max_num_candidates ?? 10000}
          step={10}
          disabled={settings.exact}
          placeholder={`${settings.limit * perResult}`}
          value={settings.numCandidates ?? ""}
          onChange={(e) =>
            onChange({
              ...settings,
              numCandidates:
                e.target.value === "" ? null : Math.max(settings.limit, Number(e.target.value)),
            })
          }
        />
      </label>
      <div className="field">
        <span>Search</span>
        <Tabs
          value={settings.exact ? "exact" : "ann"}
          options={[
            { value: "ann", label: "ANN" },
            { value: "exact", label: "Exact" },
          ]}
          label="Search type"
          onChange={(v) => onChange({ ...settings, exact: v === "exact" })}
        />
      </div>
    </div>
  );
}
