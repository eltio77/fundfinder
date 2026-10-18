import type { Holding } from "../lib/api";
import { Num } from "./ui";

export function HoldingsTable({ holdings }: { holdings: Holding[] }) {
  const max = Math.max(...holdings.map((h) => h.weight), 0);
  return (
    <section className="card">
      <header className="card-head">
        <h3>Top holdings</h3>
        <span className="muted small">{holdings.length} positions</span>
      </header>
      <div className="table-shell">
        <table className="tbl">
          <thead>
            <tr>
              <th>Holding</th>
              <th className="hide-sm">Relative size</th>
              <th className="num">Weight</th>
            </tr>
          </thead>
          <tbody>
            {holdings.map((h) => (
              <tr key={h.name}>
                <td>{h.name}</td>
                <td className="hide-sm">
                  <span className="bar">
                    <span style={{ transform: `scaleX(${max ? h.weight / max : 0})` }} />
                  </span>
                </td>
                <td className="num">
                  <Num value={h.weight * 100} digits={2} suffix="%" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
