import type { ReactNode } from "react";

import { useExpert } from "../lib/hooks";

const STEPS = [
  {
    tone: "forest",
    n: "01",
    title: "Reads the description",
    tag: "Language AI",
    body: "Each fund's objective, holdings and regions are read by an AI language model, so “UK dividend income” finds income funds even when they use different words.",
    expert: "voyage-4 via Atlas Automated Embedding · 1024 dims · ANN over profile_auto",
  },
  {
    tone: "cream",
    n: "02",
    title: "Compares what it holds",
    tag: "Portfolio mix",
    body: "Each fund's mix of sectors, regions and asset types is compared. Funds that hold similar things sit close together, whatever they are called.",
    expert: "26-dim exposure vector · cosine · ANN over exposure_vec",
  },
  {
    tone: "lilac",
    n: "03",
    title: "Combines both",
    tag: "Best match",
    body: "Funds that rank well on both lists rise to the top. This is what you see as “Funds like this” on every fund page.",
    expert: "Reciprocal rank fusion, k = 60, each list fetched 2 × limit deep",
  },
];

/** The three similarity methods as coloured blocks (the part of the dashboard design worth keeping). */
export function Methodology({
  title = "How Fund Finder matches funds",
  lead,
  aside,
}: {
  title?: string;
  lead?: ReactNode;
  aside?: ReactNode;
}) {
  const expert = useExpert();
  return (
    <section className="card method" id="how">
      <header className="method-head">
        <div>
          <h2>{title}</h2>
          {lead && <p>{lead}</p>}
        </div>
        {aside}
      </header>
      <div className="mix mix-modes">
        {STEPS.map((s) => (
          <div className="mix-item" key={s.n}>
            <span className={`dot sw-${s.tone}`} />
            <span className="mix-val">
              {s.n} <span className="faded">{s.tag}</span>
            </span>
            <span className="mix-name">{s.title}</span>
            <span className={`mix-block sw-${s.tone}`} />
            <p className="mix-body">{s.body}</p>
            {expert && <p className="mix-expert">{s.expert}</p>}
          </div>
        ))}
      </div>
    </section>
  );
}
