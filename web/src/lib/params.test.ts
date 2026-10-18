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
