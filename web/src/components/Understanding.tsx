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
  const { applied, text } = interpretation;
  if (applied.length === 0 && ignored.length === 0 && !expert) return null;

  return (
    <div className="understood" aria-label="How your search was understood">
      {applied.length > 0 && <span className="understood-label">Understood as</span>}
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
          Restore {ignored.length === 1 ? "removed rule" : `${ignored.length} removed rules`}
        </button>
      )}
      {expert && text !== q && (
        <span className="understood-text mono" title="Text sent for embedding">
          embedded: “{text}”
        </span>
      )}
    </div>
  );
}
