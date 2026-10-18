import { useState } from "react";

import type { Holding } from "../lib/api";
import { Num } from "./ui";

export function HoldingsTable({ holdings, initial = 5 }: { holdings: Holding[]; initial?: number }) {
  const [all, setAll] = useState(false);
  const max = Math.max(...holdings.map((h) => h.weight), 0);
  const shown = all ? holdings : holdings.slice(0, initial);
  return (
    <section className="card">
      <header className="card-head">
        <div>
          <h3>Biggest holdings</h3>
          <p className="card-head-sub">Share of the fund in each investment</p>
        </div>
      </header>
      <div className="table-shell">
        <table className="tbl">
          <thead>
            <tr>
              <th>Investment</th>
              <th className="hide-sm" aria-label="Relative size" />
              <th className="num">Share</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((h) => (
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
      {holdings.length > initial && (
        <button type="button" className="btn-ghost more" onClick={() => setAll(!all)}>
          {all ? "Show fewer" : `Show all ${holdings.length}`}
        </button>
      )}
    </section>
  );
}
