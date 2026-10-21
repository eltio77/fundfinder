import { useExpert } from "../lib/hooks";

const STEPS = [
  {
    title: "You describe it",
    body: "Say what you want the fund to invest in, in your own words. No fund names or jargon needed.",
  },
  {
    title: "AI reads your words",
    body: "Limits like “under 0.2%”, “index funds” or “not tech” become filters, shown as “Understood as”. The rest becomes a “meaning fingerprint”: a list of numbers that captures what you meant, not just the words you used.",
    expert: "Atlas embeds q with voyage-4 at query time",
  },
  {
    title: "Every fund is compared",
    body: "Each fund's description has a fingerprint too. Fund Finder finds the ones closest to yours.",
    expert: "$vectorSearch on profile_auto · numCandidates = 20 × limit",
  },
  {
    title: "Best matches first",
    body: "You see the closest funds first. Ask for “low cost” or “cheapest” and those matches are shown cheapest first; “highest cost” or “most expensive” puts the dearest first.",
  },
];

const TERMS = [
  {
    term: "Strong, good or loose match",
    body: "How close a fund is to what you described. On a fund page, “similar description and holdings” means both methods agree.",
  },
  {
    term: "Annual cost",
    body: "What the fund charges each year, as a share of what you invest (the OCF). 0.10% on £10,000 is £10 a year.",
  },
  {
    term: "Index fund",
    body: "Follows a market, such as the FTSE 100, rather than picking shares. Usually cheaper.",
  },
  {
    term: "Actively managed",
    body: "A manager picks investments, aiming to do better than the market. Usually costs more.",
  },
];

const TIPS = [
  ["Name what it should hold", "“UK government bonds” works better than “a safe fund”."],
  ["Add a place or theme", "Japan, healthcare, emerging markets, technology."],
  ["Say if cost matters", "“Low cost” puts the cheapest matches first, “highest cost” the most expensive."],
  ["Set limits in words", "“Index funds under 0.2%” or “global equity, not tech” become filters. Remove any you don't want."],
  ["Explore from a fund", "Open any result to see the funds most like it."],
];

const FAQ = [
  {
    q: "Is this investment advice?",
    a: "No. It's a prototype for finding funds, and nothing here is a recommendation. Read a fund's factsheet and key information document before investing, and speak to an adviser if you're unsure.",
  },
  {
    q: "Why does a result not use my words?",
    a: "Fund Finder matches on meaning, not keywords. A search for “dividends from big UK companies” finds UK equity income funds even if they never say “dividend”.",
  },
  {
    q: "What doesn't it look at?",
    a: "Past performance, risk ratings, fund size and star ratings. It finds funds that are similar in what they do and what they hold; it doesn't judge whether they're good.",
  },
  {
    q: "What does “Interpret with AI” do?",
    a: "It's an optional mode, off by default. An AI model reads what you mean rather than just your words: it fixes typos and turns vague wording into specific funds, so “cheap well known UK” finds cheap FTSE 100 trackers. It shows how it read your search, and you can remove anything it got wrong.",
  },
  {
    q: "Where does the data come from?",
    a: "Real UK funds (Open Ended Investment Companies) from Morningstar: names, providers, costs, objectives, top holdings and how each fund splits across sectors, regions and asset types. One share class is shown per fund.",
  },
];

/** The longer "How it works" content for the search page: a walkthrough, glossary, tips and FAQ. */
export function HowItWorksGuide() {
  const expert = useExpert();
  return (
    <div className="guide">
      <div className="guide-grid">
        <section>
          <h3>Your search, step by step</h3>
          <ol className="guide-steps">
            {STEPS.map((s) => (
              <li key={s.title}>
                <b>{s.title}</b>
                <p>{s.body}</p>
                {expert && s.expert && <p className="mix-expert">{s.expert}</p>}
              </li>
            ))}
          </ol>
        </section>
        <section>
          <h3>Reading your results</h3>
          <dl className="guide-terms">
            {TERMS.map((t) => (
              <div key={t.term}>
                <dt>{t.term}</dt>
                <dd>{t.body}</dd>
              </div>
            ))}
          </dl>
        </section>
        <section>
          <h3>Tips for better searches</h3>
          <ul className="guide-tips">
            {TIPS.map(([title, body]) => (
              <li key={title}>
                <b>{title}</b>
                <p>{body}</p>
              </li>
            ))}
          </ul>
        </section>
      </div>
      <section className="guide-faq">
        <h3>Good to know</h3>
        {FAQ.map((f) => (
          <details key={f.q}>
            <summary>{f.q}</summary>
            <p>{f.a}</p>
          </details>
        ))}
      </section>
    </div>
  );
}
