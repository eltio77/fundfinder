import type { Hit, Mode } from "../lib/api";
import { score, scoreFill } from "../lib/format";
import { useMeta } from "../lib/hooks";
import { Fingerprint } from "./Fingerprint";
import { Link, Num, ScoreBar } from "./ui";

export function ResultsTable({ hits, mode }: { hits: Hit[]; mode: Mode | null }) {
  const meta = useMeta();
  return (
    <div className="table-shell">
      <table className="tbl tbl-results">
        <thead>
          <tr>
            <th>Fund</th>
            <th className="hide-sm">IA sector</th>
            <th className="hide-md">Exposure</th>
            <th className="num">OCF</th>
            <th className="num">Score</th>
          </tr>
        </thead>
        <tbody>
          {hits.map((h) => (
            <tr key={h.id}>
              <td>
                <Link to={`/fund/${h.id}`} className="fund-link">
                  {h.name}
                </Link>
                <span className="sub">
                  {h.is_passive ? <span className="pill pill-green">Index</span> : null}
                  {h.tracked_index ?? h.asset_class}
                </span>
              </td>
              <td className="hide-sm muted">{h.ia_sector}</td>
              <td className="hide-md">
                <Fingerprint vector={h.exposure_vector} layout={meta?.exposure_layout ?? null} />
              </td>
              <td className="num">
                <Num value={h.ocf} digits={2} suffix="%" />
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
