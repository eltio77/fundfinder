import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

import { ApiError, type Meta } from "./api";

const MAX_RATE_LIMIT_RETRIES = 3;
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
