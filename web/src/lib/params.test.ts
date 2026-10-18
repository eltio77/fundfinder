import { describe, expect, it } from "vitest";

import { readQuery, writeQuery } from "./params";

describe("sort in the URL", () => {
  it("defaults to auto and leaves it out of the URL", () => {
    expect(readQuery(new URLSearchParams("q=cheap")).sort).toBe("auto");
    expect(writeQuery("cheap", {}, { limit: 10, numCandidates: null, exact: false })).toBe("?q=cheap");
  });

  it("round-trips an explicit choice and ignores junk", () => {
    const url = writeQuery("cheap", {}, { limit: 10, numCandidates: null, exact: false }, "relevance");
    expect(readQuery(new URLSearchParams(url)).sort).toBe("relevance");
    expect(readQuery(new URLSearchParams("q=x&sort=price")).sort).toBe("auto");
    expect(readQuery(new URLSearchParams("q=x&sort=cost_desc")).sort).toBe("cost_desc");
  });
});

describe("ignored constraints in the URL", () => {
  const settings = { limit: 10, numCandidates: null, exact: false };

  it("round-trips repeated ignore keys", () => {
    const url = writeQuery("index funds", {}, settings, "auto", ["is_passive", "not_region:UK"]);
    expect(url).toBe("?q=index+funds&ignore=is_passive&ignore=not_region%3AUK");
    expect(readQuery(new URLSearchParams(url)).ignore).toEqual(["is_passive", "not_region:UK"]);
  });
});

describe("AI interpretation mode in the URL", () => {
  it("is off by default and round-trips as intent=llm", () => {
    const settings = { limit: 10, numCandidates: null, exact: false };
    expect(readQuery(new URLSearchParams("q=x")).ai).toBe(false);
    const url = writeQuery("cheap well known uk", {}, settings, "auto", [], true);
    expect(url).toBe("?q=cheap+well+known+uk&intent=llm");
    expect(readQuery(new URLSearchParams(url)).ai).toBe(true);
  });
});

describe("untrusted URL values", () => {
  it("falls back to defaults for out-of-range or non-integer limit and nc", () => {
    for (const bad of ["0", "-5", "2.5", "101", "1e9", "abc"]) {
      expect(readQuery(new URLSearchParams(`q=x&limit=${bad}`)).settings.limit).toBe(10);
    }
    for (const bad of ["0", "-5", "2.5", "10001", "1e9", "abc"]) {
      expect(readQuery(new URLSearchParams(`q=x&nc=${bad}`)).settings.numCandidates).toBeNull();
    }
    const { settings } = readQuery(new URLSearchParams("q=x&limit=50&nc=1000"));
    expect(settings).toMatchObject({ limit: 50, numCandidates: 1000 });
  });

  it("drops a negative cost cap", () => {
    expect(readQuery(new URLSearchParams("q=x&ocf_max=-1")).filters.ocf_max).toBeUndefined();
    expect(readQuery(new URLSearchParams("q=x&ocf_max=0.25")).filters.ocf_max).toBe(0.25);
  });

  it("caps the query at the API's maximum length", () => {
    expect(readQuery(new URLSearchParams({ q: "a".repeat(5000) })).q).toHaveLength(2000);
  });

  it("dedupes, drops empty and caps ignored keys", () => {
    const p = new URLSearchParams();
    for (const k of ["a", "a", "", "b"]) p.append("ignore", k);
    expect(readQuery(p).ignore).toEqual(["a", "b"]);
    const many = new URLSearchParams();
    for (let i = 0; i < 200; i++) many.append("ignore", `k${i}`);
    expect(readQuery(many).ignore).toHaveLength(50);
  });
});
