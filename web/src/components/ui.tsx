import type { AnchorHTMLAttributes, CSSProperties, ReactNode } from "react";

import { ApiError } from "../lib/api";
import { navigate } from "../lib/router";

export function Link({
  to,
  children,
  ...rest
}: { to: string; children: ReactNode } & AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a
      href={to}
      {...rest}
      onClick={(e) => {
        rest.onClick?.(e);
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
        e.preventDefault();
        navigate(to);
      }}
    >
      {children}
    </a>
  );
}

export function ScoreBar({ fill, label }: { fill: number; label: string }) {
  return (
    <span className="score">
      <span className="score-track" aria-hidden>
        <span className="score-fill" style={{ transform: `scaleX(${fill})` }} />
      </span>
      <span className="mono">{label}</span>
    </span>
  );
}

export function Skeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="skeleton" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <span key={i} style={{ "--i": i } as CSSProperties} />
      ))}
    </div>
  );
}

export function ErrorNote({
  error,
  retryIn,
  onRetry,
}: {
  error: Error;
  retryIn: number | null;
  onRetry: () => void;
}) {
  if (error instanceof ApiError && error.rateLimited) {
    return (
      <div className="note note-wait" role="status">
        <strong>Voyage rate limit</strong>
        <p>
          Query text is embedded by Voyage at search time. Keys without a payment method allow
          3 requests a minute.
        </p>
        <p className="mono">{retryIn !== null ? `Retrying in ${retryIn}s…` : "Gave up after 3 tries."}</p>
        {retryIn === null && (
          <button type="button" className="btn-link" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    );
  }
  return (
    <div className="note note-error" role="alert">
      <strong>{error instanceof ApiError ? `Error ${error.status}` : "Request failed"}</strong>
      <p>{error.message}</p>
      <button type="button" className="btn-link" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

export function Toggle({
  checked,
  onChange,
  children,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  children: ReactNode;
}) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="toggle-track" aria-hidden>
        <span className="toggle-knob" />
      </span>
      <span>{children}</span>
    </label>
  );
}
