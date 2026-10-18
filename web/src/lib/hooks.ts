import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

import { ApiError, type Meta } from "./api";

export const MAX_RATE_LIMIT_RETRIES = 3;
const DEFAULT_RETRY_S = 20;

export interface RequestState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  /** Seconds until an automatic retry after a 429, else null. */
  retryIn: number | null;
  reload: () => void;
}

/**
 * Runs `fn` whenever `key` changes. Aborts stale requests. On 429 (Voyage rate
 * limit surfaced by the API) waits Retry-After and retries a few times, exposing
 * a countdown so the UI can say what is happening. `key: null` = don't fetch.
 */
export function useRequest<T>(
  key: string | null,
  fn: (signal: AbortSignal) => Promise<T>,
): RequestState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(false);
  const [retryIn, setRetryIn] = useState<number | null>(null);
  const [nonce, setNonce] = useState(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (key === null) return;
    const ctrl = new AbortController();
    let timer: number | undefined;
    let attempt = 0;

    const run = () => {
      setLoading(true);
      setError(null);
      setRetryIn(null);
      fnRef
        .current(ctrl.signal)
        .then((d) => {
          // A superseded request must never overwrite the newer one's result.
          if (ctrl.signal.aborted) return;
          setData(d);
          setLoading(false);
        })
        .catch((e: unknown) => {
          if (ctrl.signal.aborted) return;
          const err = e instanceof Error ? e : new Error(String(e));
          if (err instanceof ApiError && err.rateLimited && attempt < MAX_RATE_LIMIT_RETRIES) {
            attempt += 1;
            let left = err.retryAfter ?? DEFAULT_RETRY_S;
            setRetryIn(left);
            setError(err);
            timer = window.setInterval(() => {
              left -= 1;
              if (left <= 0) {
                window.clearInterval(timer);
                run();
              } else {
                setRetryIn(left);
              }
            }, 1000);
            return;
          }
          setError(err);
          setLoading(false);
        });
    };

    run();
    return () => {
      ctrl.abort();
      window.clearInterval(timer);
    };
  }, [key, nonce]);

  return { data, error, loading, retryIn, reload };
}

export const MetaContext = createContext<Meta | null>(null);
export const useMeta = () => useContext(MetaContext);

/** localStorage-backed boolean; falls back to memory if storage is unavailable. */
export function usePersistentFlag(name: string, initial: boolean): [boolean, (v: boolean) => void] {
  const [value, setValue] = useState<boolean>(() => {
    try {
      const raw = window.localStorage.getItem(name);
      return raw === null ? initial : raw === "1";
    } catch {
      return initial;
    }
  });
  const set = useCallback(
    (v: boolean) => {
      setValue(v);
      try {
        window.localStorage.setItem(name, v ? "1" : "0");
      } catch {
        /* storage blocked: keep in memory only */
      }
    },
    [name],
  );
  return [value, set];
}

function readJson<T>(name: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(name);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(name: string, value: unknown): void {
  try {
    window.localStorage.setItem(name, JSON.stringify(value));
  } catch {
    /* storage blocked */
  }
}

export type Theme = "light" | "dark";

/** Explicit theme choice wins; otherwise follow the OS. */
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() => {
    const saved = readJson<Theme | null>("ff.theme", null);
    if (saved) return saved;
    return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      writeJson("ff.theme", next);
      return next;
    });
  }, []);
  return [theme, toggle];
}

export const ExpertContext = createContext(false);
export const useExpert = () => useContext(ExpertContext);
