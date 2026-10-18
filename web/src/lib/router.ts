import { useSyncExternalStore } from "react";

// Two routes don't justify a router dependency: "/" (search) and "/fund/:id".

const NAV_EVENT = "fundfinder:navigate";

function subscribe(onChange: () => void): () => void {
  window.addEventListener("popstate", onChange);
  window.addEventListener(NAV_EVENT, onChange);
  return () => {
    window.removeEventListener("popstate", onChange);
    window.removeEventListener(NAV_EVENT, onChange);
  };
}

const snapshot = () => window.location.pathname + window.location.search;

/** Path of a fund page; ids come from the API, so encode them like any other data. */
export const fundPath = (id: string) => `/fund/${encodeURIComponent(id)}`;

/** True when the previous history entry is a page of this app (we pushed this one). */
export const canGoBackInApp = (): boolean =>
  (window.history.state as { inApp?: boolean } | null)?.inApp === true;

export function navigate(to: string, { replace = false } = {}): void {
  if (to === snapshot()) return;
  if (replace) window.history.replaceState(window.history.state, "", to);
  else window.history.pushState({ inApp: true }, "", to);
  window.dispatchEvent(new Event(NAV_EVENT));
  if (!replace) window.scrollTo({ top: 0 });
}

export type Route =
  | { name: "search"; params: URLSearchParams }
  | { name: "fund"; id: string; params: URLSearchParams }
  | { name: "notFound" };

export function matchRoute(url: string): Route {
  const [path, query = ""] = url.split("?");
  const params = new URLSearchParams(query);
  if (path === "/" || path === "") return { name: "search", params };
  const m = /^\/fund\/([^/]+)\/?$/.exec(path);
  if (m) {
    try {
      return { name: "fund", id: decodeURIComponent(m[1]), params };
    } catch {
      // Malformed escape (e.g. /fund/%E0) would otherwise throw during render.
      return { name: "notFound" };
    }
  }
  return { name: "notFound" };
}

export function useRoute(): Route {
  return matchRoute(useSyncExternalStore(subscribe, snapshot));
}
