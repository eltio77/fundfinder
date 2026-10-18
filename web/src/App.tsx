import { IconArrowUpRight, IconMoon, IconSun, Logo } from "./components/Icons";
import { Link, Toggle } from "./components/ui";
import { api } from "./lib/api";
import { ExpertContext, MetaContext, usePersistentFlag, useRequest, useTheme } from "./lib/hooks";
import { useRoute } from "./lib/router";
import { FundPage } from "./pages/FundPage";
import { SearchPage } from "./pages/SearchPage";

export function App() {
  const route = useRoute();
  const [theme, toggleTheme] = useTheme();
  const [expert, setExpert] = usePersistentFlag("ff.expert", false);
  const meta = useRequest("meta", (signal) => api.meta(signal));
  const apiUp = meta.error ? false : meta.data ? true : null;

  return (
    <MetaContext.Provider value={meta.data}>
      <ExpertContext.Provider value={expert}>
        <div className="frame">
          <div className="panel">
            <header className="topnav">
              <Link to="/" className="brand">
                <Logo />
                <span>Fund Finder</span>
              </Link>
              <nav className="topnav-links">
                <Link to="/">Search</Link>
                <a href="/#how">How it works</a>
              </nav>
              <div className="topnav-actions">
                <span
                  className={`status-dot ${apiUp === null ? "" : apiUp ? "up" : "down"}`}
                  title={apiUp === null ? "Connecting" : apiUp ? "Connected" : "API unavailable"}
                />
                <a className="nav-api" href="/docs" target="_blank" rel="noreferrer" title="Swagger API docs">
                  API <IconArrowUpRight width={14} height={14} />
                </a>
                <Toggle checked={expert} onChange={setExpert}>
                  Expert mode
                </Toggle>
                <button
                  type="button"
                  className="icon-btn"
                  aria-label={theme === "dark" ? "Light mode" : "Dark mode"}
                  title={theme === "dark" ? "Light mode" : "Dark mode"}
                  onClick={toggleTheme}
                >
                  {theme === "dark" ? <IconSun /> : <IconMoon />}
                </button>
              </div>
            </header>

            <main className="content">
              {route.name === "search" && <SearchPage params={route.params} />}
              {route.name === "fund" && <FundPage id={route.id} />}
              {route.name === "notFound" && (
                <div className="card">
                  <p>That page doesn't exist.</p>
                  <Link to="/" className="btn-ghost">
                    Back to search
                  </Link>
                </div>
              )}
            </main>

            <footer className="foot">
              <span>Prototype with synthetic data. Not investment information or advice.</span>
            </footer>
          </div>
        </div>
      </ExpertContext.Provider>
    </MetaContext.Provider>
  );
}
