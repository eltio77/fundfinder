import { describe, expect, it } from "vitest";

import { AI_FALLBACK_NOTICE, ApiError, parseRetryAfter, type SearchResponse, withAiFallback } from "./api";

describe("parseRetryAfter", () => {
  it("reads delay-seconds", () => {
    expect(parseRetryAfter("20")).toBe(20);
    expect(parseRetryAfter(" 5 ")).toBe(5);
  });

  it("reads an HTTP date relative to now", () => {
    const now = Date.parse("2026-01-01T00:00:00Z");
    expect(parseRetryAfter("Thu, 01 Jan 2026 00:00:30 GMT", now)).toBe(30);
  });

  it("clamps to 1..120 seconds", () => {
    expect(parseRetryAfter("0")).toBe(1);
    expect(parseRetryAfter("86400")).toBe(120);
    const now = Date.parse("2026-01-01T00:00:00Z");
    expect(parseRetryAfter("Wed, 31 Dec 2025 00:00:00 GMT", now)).toBe(1);
  });

  it("returns null when absent or unparseable (never NaN)", () => {
    expect(parseRetryAfter(null)).toBeNull();
    expect(parseRetryAfter("")).toBeNull();
    expect(parseRetryAfter("soon")).toBeNull();
    expect(parseRetryAfter("-5")).toBeNull();
  });
});

const response = (source: "rules" | "llm"): SearchResponse => ({
  query: "cheap well known uk",
  fund_id: null,
  mode: null,
  sort: "relevance",
  interpretation: { source, text: "uk", applied: [], summary: null, notice: null },
  limit: 10,
  num_candidates: 200,
  exact: false,
  filters: {},
  took_ms: 12,
  results: [],
});

describe("withAiFallback", () => {
  it("does not touch the AI path when AI is off", async () => {
    const calls: boolean[] = [];
    await withAiFallback(false, async (ai) => (calls.push(ai), response("rules")));
    expect(calls).toEqual([false]);
  });

  it("returns the AI result when it succeeds", async () => {
    const res = await withAiFallback(true, async (ai) => response(ai ? "llm" : "rules"));
    expect(res.interpretation?.source).toBe("llm");
    expect(res.interpretation?.notice).toBeNull();
  });

  it.each([429, 503])("falls back to the standard reading on %i and says so", async (status) => {
    const calls: boolean[] = [];
    const res = await withAiFallback(true, async (ai) => {
      calls.push(ai);
      if (ai) throw new ApiError(status, "busy", 20);
      return response("rules");
    });
    expect(calls).toEqual([true, false]);
    expect(res.interpretation?.source).toBe("rules");
    expect(res.interpretation?.notice).toBe(AI_FALLBACK_NOTICE);
  });

  it("propagates other errors without a second request", async () => {
    const calls: boolean[] = [];
    const run = async (ai: boolean): Promise<SearchResponse> => {
      calls.push(ai);
      throw new ApiError(422, "bad request");
    };
    await expect(withAiFallback(true, run)).rejects.toMatchObject({ status: 422 });
    expect(calls).toEqual([true]);
  });

  it("propagates a failure of the fallback search itself", async () => {
    const run = async (): Promise<SearchResponse> => {
      throw new ApiError(429, "embedding provider rate limit exceeded", 20);
    };
    await expect(withAiFallback(true, run)).rejects.toMatchObject({ status: 429 });
  });
});
