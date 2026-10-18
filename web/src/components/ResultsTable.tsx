import type { CSSProperties } from "react";

import type { Hit, Mode } from "../lib/api";
import { ocf, score, scoreFill } from "../lib/format";
import { useMeta } from "../lib/hooks";
import { Fingerprint } from "./Fingerprint";
import { Link, ScoreBar } from "./ui";

export function ResultsTable({ hits, mode }: { hits: Hit[]; mode: Mode | null }) {
  const meta = useMeta();
  return (
    <div className="table-wrap">
      <table className="results">
        <thead>
          <tr>
            <th className="num">#</th>
            <th>Fund</th>
            <th className="hide-sm">IA sector</th>
            <th className="num">OCF</th>
            <th className="hide-md">Exposure</th>
            <th className="num">Score</th>
          </tr>
        </thead>
        <tbody>
          {hits.map((h, i) => (
            <tr key={h.id} style={{ "--i": i } as CSSProperties}>
              <td className="num rank">{String(i + 1).padStart(2, "0")}</td>
              <td>
                <Link to={`/fund/${h.id}`} className="fund-link">
                  {h.name}
                </Link>
                <span className="sub">
                  {h.is_passive && <span className="tag">Index</span>}
                  {h.tracked_index ?? h.asset_class}
                </span>
              </td>
              <td className="hide-sm muted">{h.ia_sector}</td>
              <td className="num mono">{ocf(h.ocf)}</td>
              <td className="hide-md">
                <Fingerprint vector={h.exposure_vector} layout={meta?.exposure_layout ?? null} />
              </td>
              <td className="num">
                <ScoreBar fill={scoreFill(h.score, mode)} label={score(h.score, mode)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
