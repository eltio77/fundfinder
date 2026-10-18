import type { Hit } from "../lib/api";
import { matchReason, STRENGTH_LABEL, score, strength, type Strength } from "../lib/format";
import { useExpert, useMeta } from "../lib/hooks";
import { fundPath } from "../lib/router";
import { Fingerprint } from "./Fingerprint";
import { IconArrowUpRight } from "./Icons";
import { Link, Num } from "./ui";

/**
 * Funds as plain-language rows: what it is, what it costs, how well it matches.
 * `fused` rows explain *why* they matched (description, holdings or both).
 */
export function ResultList({
  hits,
  fused = false,
  clusterId = null,
}: {
  hits: Hit[];
  fused?: boolean;
  clusterId?: string | null;
}) {
  const expert = useExpert();
  const meta = useMeta();

  return (
    <ol className="results">
      {hits.map((h, i) => {
        const reason = fused ? matchReason(h.ranks, hits.length) : null;
        const s: Strength = reason ? reason.strength : strength(h.score);
        const sibling = expert && clusterId !== null && h.cluster_id === clusterId;
        return (
          <li key={h.id} className="result" style={{ animationDelay: `${i * 35}ms` }}>
            <div className="result-main">
              <Link to={fundPath(h.id)} className="result-name">
                {h.name}
              </Link>
              <p className="result-meta">
                {h.is_passive ? (
                  <>
                    Index fund tracking the <b>{h.tracked_index?.replace(/ Index$/, "")}</b>
                  </>
                ) : (
                  <>Actively managed</>
                )}{" "}
                · {h.ia_sector}
              </p>
              {expert && (
                <p className="result-expert">
                  <Fingerprint vector={h.exposure_vector} layout={meta?.exposure_layout ?? null} />
                  <span className="mono">
                    {h.id} · score {score(h.score, fused ? "both" : "text")}
                    {h.ranks && ` · T${h.ranks.text ?? "–"} E${h.ranks.exposure ?? "–"}`}
                  </span>
                  {sibling && <span className="pill pill-green">sibling</span>}
                </p>
              )}
            </div>
            <div className="result-cost">
              <span className="result-label">Annual cost</span>
              <span className="result-value">
                <Num value={h.ocf} digits={2} suffix="%" />
              </span>
            </div>
            <div className="result-match">
              <span className={`match match-${s}`}>
                <span className="match-dots" aria-hidden>
                  <i />
                  <i />
                  <i />
                </span>
                {reason ? reason.label : STRENGTH_LABEL[s]}
              </span>
            </div>
            <Link to={fundPath(h.id)} className="result-go" aria-label={`Open ${h.name}`}>
              <IconArrowUpRight width={18} height={18} />
            </Link>
          </li>
        );
      })}
    </ol>
  );
}
