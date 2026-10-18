import type { Meta, SearchSettings } from "../lib/api";
import { Tabs } from "./ui";

const LIMITS = [5, 10, 20, 50];

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
