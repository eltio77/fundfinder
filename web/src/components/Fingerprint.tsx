import { type CSSProperties, useState } from "react";

import type { ExposureLayout } from "../lib/api";
import { intensities } from "../lib/format";

const BLOCKS = [
  { key: "sectors", label: "Sectors", tone: "forest" },
  { key: "regions", label: "Regions", tone: "lilac" },
  { key: "asset_classes", label: "Assets", tone: "amber" },
] as const;

interface Props {
  vector: number[] | null | undefined;
  layout: ExposureLayout | null;
  size?: "sm" | "lg";
}

/**
 * The 26-dim exposure vector drawn as a barcode: sectors | regions | asset classes.
 * Cell intensity is the weight relative to the vector's own maximum, so two funds
 * with similar fingerprints have similar exposure regardless of scale.
 */
export function Fingerprint({ vector, layout, size = "sm" }: Props) {
  const [focus, setFocus] = useState<string | null>(null);
  if (!vector || !layout) return <span className={`fp fp-${size} fp-empty`} aria-hidden />;

  const levels = intensities(vector);
  let offset = 0;
  const groups = BLOCKS.map((b) => {
    const labels = layout[b.key];
    const cells = labels.map((label, i) => ({
      label,
      raw: vector[offset + i],
      level: levels[offset + i],
    }));
    offset += labels.length;
    return { ...b, cells };
  });

  const summary = groups
    .map((g) => {
      const top = [...g.cells].sort((a, b) => b.raw - a.raw)[0];
      return top && top.raw > 0 ? `${g.label}: mostly ${top.label}` : null;
    })
    .filter(Boolean)
    .join("; ");

  return (
    <span className={`fp fp-${size}`} role="img" aria-label={`Exposure fingerprint. ${summary}`}>
      <span className="fp-strip">
        {groups.map((g) => (
          <span key={g.key} className={`fp-group fp-${g.tone}`}>
            {g.cells.map((c, i) => (
              <span
                key={c.label}
                className="fp-cell"
                style={{ "--lvl": c.level, "--i": i } as CSSProperties}
                title={`${c.label} · ${c.raw.toFixed(3)}`}
                onMouseEnter={size === "lg" ? () => setFocus(`${g.label} — ${c.label}`) : undefined}
                onMouseLeave={size === "lg" ? () => setFocus(null) : undefined}
              />
            ))}
          </span>
        ))}
      </span>
      {size === "lg" && (
        <span className="fp-legend">
          {groups.map((g) => (
            <span key={g.key} className={`fp-legend-item fp-${g.tone}`} style={{ flex: g.cells.length }}>
              {g.label}
            </span>
          ))}
        </span>
      )}
      {size === "lg" && <span className="fp-focus">{focus ?? "Hover a cell to read it"}</span>}
    </span>
  );
}
