import { describe, expect, it } from "vitest";

import { fundPath, matchRoute } from "./router";

describe("fund routes", () => {
  it("round-trips ids that need encoding", () => {
    for (const id of ["GB00B3X7QG63", "a/b", "x?y=1#z", "50% off"]) {
      expect(matchRoute(fundPath(id))).toMatchObject({ name: "fund", id });
    }
  });

  it("treats a malformed escape as not found instead of throwing", () => {
    expect(matchRoute("/fund/%E0")).toEqual({ name: "notFound" });
  });
});
