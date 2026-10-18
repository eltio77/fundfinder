import { Shell } from "./components/Shell";
import { Link } from "./components/ui";
import { api } from "./lib/api";
import { MetaContext, useRequest, useTheme } from "./lib/hooks";
import { useRoute } from "./lib/router";
import { FundPage } from "./pages/FundPage";
import { SearchPage } from "./pages/SearchPage";

function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export function App() {
  const route = useRoute();
  const [theme, toggleTheme] = useTheme();
  const meta = useRequest("meta", (signal) => api.meta(signal));
  const clusters = useRequest("clusters", (signal) => api.clusters(signal));

  const title =
    route.name === "fund" ? (
      <span className="crumbs">
        <Link to="/">Search</Link>
        <span aria-hidden>/</span>
        <span>{route.id}</span>
      </span>
    ) : route.name === "search" ? (
      `${greeting()}`
    ) : (
      "Not found"
    );
  const subtitle =
    route.name === "search" ? "Find UK funds that hold and behave alike." : undefined;

  return (
    <MetaContext.Provider value={meta.data}>
      <Shell
        route={route}
        clusters={clusters.data}
        embedModel={meta.data?.embed_model ?? null}
        apiUp={meta.error ? false : meta.data ? true : null}
        theme={theme}
        onToggleTheme={toggleTheme}
        title={title}
        subtitle={subtitle}
      >
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
      </Shell>
    </MetaContext.Provider>
  );
}
