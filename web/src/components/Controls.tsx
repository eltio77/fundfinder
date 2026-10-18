import type { Filters, Meta, SearchSettings } from "../lib/api";

const LIMITS = [5, 10, 20, 50];

export function FilterBar({
  filters,
  onChange,
  meta,
}: {
  filters: Filters;
  onChange: (f: Filters) => void;
  meta: Meta | null;
}) {
  const set = (patch: Partial<Filters>) => onChange({ ...filters, ...patch });
  const active = Object.values(filters).some((v) => v !== undefined);
  return (
    <fieldset className="controls">
      <legend>Filters</legend>
      <label className="field">
        <span>Asset class</span>
        <select
          value={filters.asset_class ?? ""}
          onChange={(e) => set({ asset_class: e.target.value || undefined })}
        >
          <option value="">Any</option>
          {meta?.asset_classes.map((a) => <option key={a}>{a}</option>)}
        </select>
      </label>
      <label className="field field-wide">
        <span>IA sector</span>
        <select
          value={filters.ia_sector ?? ""}
          onChange={(e) => set({ ia_sector: e.target.value || undefined })}
        >
          <option value="">Any</option>
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
      <div className="field">
        <span>Management</span>
        <div className="segmented" role="radiogroup" aria-label="Management">
          {(
            [
              ["Any", undefined],
              ["Passive", true],
              ["Active", false],
            ] as const
          ).map(([label, value]) => (
            <button
              key={label}
              type="button"
              role="radio"
              aria-checked={filters.is_passive === value}
              className={filters.is_passive === value ? "on" : ""}
              onClick={() => set({ is_passive: value })}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {active && (
        <button type="button" className="btn-link clear" onClick={() => onChange({})}>
          Clear
        </button>
      )}
    </fieldset>
  );
}

export function SettingsBar({
  settings,
  onChange,
  meta,
}: {
  settings: SearchSettings;
  onChange: (s: SearchSettings) => void;
  meta: Meta | null;
}) {
  const perResult = meta?.defaults.candidates_per_result ?? 20;
  const effective = settings.numCandidates ?? settings.limit * perResult;
  return (
    <fieldset className="controls controls-settings">
      <legend>Query</legend>
      <label className="field field-narrow">
        <span>limit</span>
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
              numCandidates: e.target.value === "" ? null : Math.max(settings.limit, Number(e.target.value)),
            })
          }
        />
      </label>
      <div className="field">
        <span>Search</span>
        <div className="segmented" role="radiogroup" aria-label="Search type">
          <button
            type="button"
            role="radio"
            aria-checked={!settings.exact}
            className={!settings.exact ? "on" : ""}
            onClick={() => onChange({ ...settings, exact: false })}
            title={`Approximate (HNSW), ${effective} candidates`}
          >
            ANN
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={settings.exact}
            className={settings.exact ? "on" : ""}
            onClick={() => onChange({ ...settings, exact: true })}
            title="Exact nearest neighbours (full scan)"
          >
            Exact
          </button>
        </div>
      </div>
    </fieldset>
  );
}
