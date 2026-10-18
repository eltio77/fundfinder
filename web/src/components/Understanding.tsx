import type { SearchResponse } from "../lib/api";
import { useExpert } from "../lib/hooks";

/**
 * What the search read from the query ("Index funds only", "Not mainly technology"),
 * as chips the user can remove. Removing one re-runs the search without it.
 */
export function Understanding({
  q,
  interpretation,
  ignored,
  onIgnore,
  onReset,
}: {
  q: string;
  interpretation: NonNullable<SearchResponse["interpretation"]>;
  ignored: string[];
  onIgnore: (key: string) => void;
  onReset: () => void;
}) {
  const expert = useExpert();
  const { applied, text, source, summary, notice } = interpretation;
  if (
    applied.length === 0 &&
    ignored.length === 0 &&
    !expert &&
    !summary &&
    !notice
  )
    return null;

  return (
    <>
      {source === "llm" && summary && (
        <p className="ai-summary">
          <span className="pill pill-amber">AI</span> {summary}
        </p>
      )}
      {notice && <p className="ai-notice">{notice}</p>}
      <div className="understood" role="group" aria-label="How your search was understood">
        {applied.length > 0 && (
          <span className="understood-label">Understood as</span>
        )}
        {applied.map((a) => (
          <span className="understood-chip" key={a.key}>
            {a.label}
            <button
              type="button"
              aria-label={`Remove “${a.label}”`}
              title="Remove this and search again"
              onClick={() => onIgnore(a.key)}
            >
              ×
            </button>
          </span>
        ))}
        {ignored.length > 0 && (
          <button type="button" className="understood-reset" onClick={onReset}>
            Restore{" "}
            {ignored.length === 1
              ? "removed rule"
              : `${ignored.length} removed rules`}
          </button>
        )}
        {(expert || source === "llm") && text !== q && (
          <span
            className="understood-text mono"
            title="Text sent for embedding"
          >
            searched for: “{text}”
          </span>
        )}
      </div>
    </>
  );
}
