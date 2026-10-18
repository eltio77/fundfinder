import type { Filters, Meta } from "../lib/api";
import { useExpert } from "../lib/hooks";
import { Tabs } from "./ui";

type Kind = "any" | "index" | "active";

const COSTS = [
  { value: "", label: "Any cost" },
  { value: "0.25", label: "Under 0.25% a year" },
  { value: "0.5", label: "Under 0.5% a year" },
  { value: "1", label: "Under 1% a year" },
];

/** Filters in plain language. IA sector is an expert-only refinement. */
export function SimpleFilters({
  filters,
  onChange,
  meta,
}: {
  filters: Filters;
  onChange: (f: Filters) => void;
  meta: Meta | null;
}) {
  const expert = useExpert();
  const kind: Kind = filters.is_passive === undefined ? "any" : filters.is_passive ? "index" : "active";
  const cost = filters.ocf_max === undefined ? "" : String(filters.ocf_max);
  const costOptions = COSTS.some((c) => c.value === cost)
    ? COSTS
    : [...COSTS, { value: cost, label: `Under ${cost}% a year` }];

  return (
    <div className="simple-filters">
      <Tabs<Kind>
        value={kind}
        label="Fund type"
        options={[
          { value: "any", label: "All funds" },
          { value: "index", label: "Index funds" },
          { value: "active", label: "Actively managed" },
        ]}
        onChange={(v) => onChange({ ...filters, is_passive: v === "any" ? undefined : v === "index" })}
      />
      <select
        className="select-pill"
        aria-label="Asset type"
        value={filters.asset_class ?? ""}
        onChange={(e) => onChange({ ...filters, asset_class: e.target.value || undefined })}
      >
        <option value="">Any asset type</option>
        {meta?.asset_classes.map((a) => <option key={a}>{a}</option>)}
      </select>
      <select
        className="select-pill"
        aria-label="Annual cost"
        value={cost}
        onChange={(e) => onChange({ ...filters, ocf_max: e.target.value ? Number(e.target.value) : undefined })}
      >
        {costOptions.map((c) => (
          <option key={c.value} value={c.value}>
            {c.label}
          </option>
        ))}
      </select>
      {expert && (
        <select
          className="select-pill"
          aria-label="IA sector"
          value={filters.ia_sector ?? ""}
          onChange={(e) => onChange({ ...filters, ia_sector: e.target.value || undefined })}
        >
          <option value="">Any IA sector</option>
          {meta?.ia_sectors.map((s) => <option key={s}>{s}</option>)}
        </select>
      )}
    </div>
  );
}
