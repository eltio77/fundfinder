import { Link } from "./components/ui";
import { api } from "./lib/api";
import { MetaContext, useRequest } from "./lib/hooks";
import { useRoute } from "./lib/router";
import { FundPage } from "./pages/FundPage";
import { SearchPage } from "./pages/SearchPage";

const today = new Intl.DateTimeFormat("en-GB", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
}).format(new Date());

export function App() {
  const route = useRoute();
  const meta = useRequest("meta", (signal) => api.meta(signal));

  return (
    <MetaContext.Provider value={meta.data}>
      <div className="grain" aria-hidden />
      <header className="masthead">
        <div className="masthead-rule mono">
          <span>{today}</span>
          <span className="hide-sm">Synthetic UK fund universe · 300 funds</span>
          <span className={`status ${meta.error ? "down" : meta.data ? "up" : ""}`}>
            {meta.error ? "API unavailable" : meta.data ? "Connected" : "Connecting"}
          </span>
        </div>
        <Link to="/" className="brand">
          Fund <em>Finder</em>
        </Link>
      </header>

      <main>
        {route.name === "search" && <SearchPage params={route.params} />}
        {route.name === "fund" && <FundPage id={route.id} />}
        {route.name === "notFound" && (
          <div className="page">
            <h1 className="display">Not found.</h1>
            <Link to="/" className="btn-link">
              ← Back to search
            </Link>
          </div>
        )}
      </main>

      <footer className="colophon mono">
        <span>Prototype · synthetic data, not investment information</span>
        <span>MongoDB Vector Search · Voyage AI · FastAPI</span>
      </footer>
    </MetaContext.Provider>
  );
}
