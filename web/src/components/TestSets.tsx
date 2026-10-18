import type { ClusterMember } from "../lib/api";
import { clusterName } from "../lib/format";
import { fundPath } from "../lib/router";
import { Link } from "./ui";

const GROUPS = [
  { prefix: "trk_", label: "Index trackers", note: "Same index, different providers" },
  { prefix: "act_", label: "Near-duplicates", note: "Shared process, holdings and wording" },
  { prefix: "outlier_", label: "Outliers", note: "No true neighbours" },
];

/** Expert mode: jump to a member of each deliberate synthetic cluster. */
export function TestSets({ clusters }: { clusters: Record<string, ClusterMember[]> | null }) {
  if (!clusters || Object.keys(clusters).length === 0) return null;
  return (
    <section className="card">
      <header className="card-head">
        <div>
          <h3>Test sets</h3>
          <p className="card-head-sub">Deliberate clusters in the synthetic data, for checking search quality.</p>
        </div>
      </header>
      <div className="testsets">
        {GROUPS.map((g) => (
          <div key={g.prefix} className="testset">
            <h4>{g.label}</h4>
            <p className="muted small">{g.note}</p>
            <ul>
              {Object.entries(clusters)
                .filter(([c]) => c.startsWith(g.prefix))
                .map(([c, members]) => (
                  <li key={c}>
                    <Link to={fundPath(members[0].id)}>{clusterName(c)}</Link>
                    <span className="muted small">{members.length}</span>
                  </li>
                ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
