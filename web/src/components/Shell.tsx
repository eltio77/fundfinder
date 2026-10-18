import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";

import type { ClusterMember } from "../lib/api";
import { clusterName } from "../lib/format";
import { type Theme, useRecent } from "../lib/hooks";
import { navigate, type Route } from "../lib/router";
import {
  IconBook,
  IconChevron,
  IconClock,
  IconFlask,
  IconLayers,
  IconMenu,
  IconMoon,
  IconSearch,
  IconSparkle,
  IconSun,
  Logo,
} from "./Icons";
import { IconButton, Link } from "./ui";

const GROUPS = [
  { prefix: "trk_", label: "Index trackers" },
  { prefix: "act_", label: "Near-duplicates" },
  { prefix: "outlier_", label: "Outliers" },
];

interface Props {
  route: Route;
  clusters: Record<string, ClusterMember[]> | null;
  embedModel: string | null;
  apiUp: boolean | null;
  theme: Theme;
  onToggleTheme: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
}

export function Shell(props: Props) {
  const { route, clusters, embedModel, apiUp, theme, onToggleTheme, title, subtitle, children } = props;
  const [open, setOpen] = useState(false);
  const recent = useRecent();
  const quick = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const [expanded, setExpanded] = useState<string | null>("trk_");

  // ⌘K / Ctrl+K focuses quick search.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(true);
        quick.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Close the mobile drawer on navigation.
  const routeKey = route.name === "fund" ? route.id : route.name;
  useEffect(() => setOpen(false), [routeKey]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!q.trim()) return;
    navigate(`/?q=${encodeURIComponent(q.trim())}`);
    setQ("");
    quick.current?.blur();
  };

  const activeFund = route.name === "fund" ? route.id : null;

  return (
    <div className={`shell ${open ? "drawer-open" : ""}`}>
      <aside className="sidebar" aria-label="Navigation">
        <Link to="/" className="brand">
          <Logo />
          <span>Fund Finder</span>
        </Link>

        <form className="quick" onSubmit={submit} role="search">
          <IconSearch width={16} height={16} />
          <input
            ref={quick}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Quick search"
            aria-label="Quick search"
          />
          <kbd>⌘</kbd>
          <kbd>K</kbd>
        </form>

        <nav className="nav">
          <Link to="/" className={`nav-item ${route.name === "search" ? "active" : ""}`}>
            <IconLayers />
            <span>Search</span>
          </Link>

          <div className="nav-section">
            <span className="nav-title">
              <IconFlask /> Test sets
            </span>
            {GROUPS.map((g) => {
              const ids = Object.keys(clusters ?? {}).filter((c) => c.startsWith(g.prefix));
              const isOpen = expanded === g.prefix;
              return (
                <div key={g.prefix} className="nav-group">
                  <button
                    type="button"
                    className={`nav-item ${isOpen ? "open" : ""}`}
                    aria-expanded={isOpen}
                    onClick={() => setExpanded(isOpen ? null : g.prefix)}
                  >
                    <IconChevron className="chev" width={15} height={15} />
                    <span>{g.label}</span>
                    <span className="count">{clusters ? ids.length : "–"}</span>
                  </button>
                  {isOpen && (
                    <ul className="nav-sub">
                      {ids.map((c) => {
                        const first = clusters![c][0];
                        const label = clusterName(c);
                        const inCluster = clusters![c].some((m) => m.id === activeFund);
                        return (
                          <li key={c}>
                            <Link
                              to={`/fund/${first.id}`}
                              className={inCluster ? "active" : ""}
                              title={`${clusters![c].length} funds: ${clusters![c].map((m) => m.name).join(", ")}`}
                            >
                              {label}
                              <span className="sub-count">{clusters![c].length}</span>
                            </Link>
                          </li>
                        );
                      })}
                      {clusters && ids.length === 0 && <li className="muted">None in this data</li>}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>

          {recent.length > 0 && (
            <div className="nav-section">
              <span className="nav-title">
                <IconClock /> Recent
              </span>
              <ul className="nav-sub nav-recent">
                {recent.map((f) => (
                  <li key={f.id}>
                    <Link to={`/fund/${f.id}`} className={f.id === activeFund ? "active" : ""}>
                      {f.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </nav>

        <div className="promo">
          <span className="promo-icon">
            <IconSparkle />
          </span>
          <strong>Atlas Vector Search</strong>
          <p>
            Profiles embedded by <b>{embedModel ?? "voyage-4"}</b> with Automated Embedding. Exposure
            vectors compared by cosine.
          </p>
          <a className="promo-btn" href="/docs" target="_blank" rel="noreferrer">
            Open API docs
          </a>
        </div>

        <div className="who">
          <span className={`status-dot ${apiUp === null ? "" : apiUp ? "up" : "down"}`} />
          <span>{apiUp === null ? "Connecting…" : apiUp ? "API connected" : "API unavailable"}</span>
          <span className="muted small">Synthetic data</span>
        </div>
      </aside>

      <button
        type="button"
        className="scrim"
        aria-label="Close menu"
        tabIndex={open ? 0 : -1}
        onClick={() => setOpen(false)}
      />

      <div className="panel">
        <header className="topbar">
          <button type="button" className="icon-btn menu-btn" aria-label="Open menu" onClick={() => setOpen(true)}>
            <IconMenu />
          </button>
          <div className="topbar-title">
            <h1>{title}</h1>
            {subtitle && <div className="topbar-sub">{subtitle}</div>}
          </div>
          <div className="topbar-actions">
            <IconButton label="API docs" href="/docs">
              <IconBook />
            </IconButton>
            <IconButton label={theme === "dark" ? "Light mode" : "Dark mode"} onClick={onToggleTheme}>
              {theme === "dark" ? <IconSun /> : <IconMoon />}
            </IconButton>
          </div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
