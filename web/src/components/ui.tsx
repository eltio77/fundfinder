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

/** Number with its trailing decimals faded, e.g. 0.51% -> "0.5" + faded "1%". */
export function Num({
  value,
  digits = 2,
  suffix = "",
  fade = 1,
}: {
  value: number;
  digits?: number;
  suffix?: string;
  fade?: number;
}) {
  const s = value.toFixed(digits);
  const cut = digits > 0 ? s.length - Math.min(fade, digits) : s.length;
  return (
    <span className="num-text">
      {s.slice(0, cut)}
      <span className="faded">
        {s.slice(cut)}
        {suffix}
      </span>
    </span>
  );
}

/** Text whose tail fades to grey, as in the reference's insight cards. */
export function FadeText({ strong, soft }: { strong: string; soft: string }) {
  return (
    <p className="fade-text">
      <span>{strong} </span>
      <span className="soft">{soft}</span>
    </p>
  );
}

export function ScoreBar({ fill, label }: { fill: number; label: string }) {
  return (
    <span className="score">
      <span className="bar" aria-hidden>
        <span style={{ transform: `scaleX(${fill})` }} />
      </span>
      <span className="score-label">{label}</span>
    </span>
  );
}

export function Tabs<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="tab"
          aria-selected={o.value === value}
          className={o.value === value ? "on" : ""}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
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
        <span className="pill pill-amber">Rate limited</span>
        <p>
          Voyage embeds query text at search time. Keys without a payment method allow 3 requests
          a minute.
        </p>
        <p className="note-foot">
          {retryIn !== null ? `Retrying in ${retryIn}s…` : "Gave up after 3 tries."}
          {retryIn === null && (
            <button type="button" className="btn-ghost" onClick={onRetry}>
              Try again
            </button>
          )}
        </p>
      </div>
    );
  }
  return (
    <div className="note note-error" role="alert">
      <span className="pill pill-coral">{error instanceof ApiError ? `Error ${error.status}` : "Failed"}</span>
      <p>{error.message}</p>
      <p className="note-foot">
        <button type="button" className="btn-ghost" onClick={onRetry}>
          Try again
        </button>
      </p>
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
