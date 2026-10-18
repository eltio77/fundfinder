import type { CSSProperties } from "react";

import { pct } from "../lib/format";

export function WeightList({
  title,
  weights,
  tone = "ink",
  limit,
}: {
  title: string;
  weights: Record<string, number> | { name: string; weight: number }[];
  tone?: "ink" | "accent" | "sage";
  limit?: number;
}) {
  const rows = (
    Array.isArray(weights)
      ? weights.map((h) => [h.name, h.weight] as const)
      : Object.entries(weights).sort((a, b) => b[1] - a[1])
  )
    .filter(([, w]) => w > 0)
    .slice(0, limit);
  const max = Math.max(...rows.map(([, w]) => w), 0);

  return (
    <div className={`weights weights-${tone}`}>
      <h4>{title}</h4>
      {rows.length === 0 ? (
        <p className="empty">None</p>
      ) : (
        <ul>
          {rows.map(([name, w], i) => (
            <li key={name} style={{ "--i": i } as CSSProperties}>
              <span className="w-name">{name}</span>
              <span className="w-val mono">{pct(w)}</span>
              <span className="w-bar" aria-hidden>
                <span style={{ transform: `scaleX(${max > 0 ? w / max : 0})` }} />
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
