import { describe, expect, it } from "vitest";

import { toQuery } from "./api";
import {
  cheaperMatches,
  clusterLabel,
  clusterSize,
  intensities,
  ocf,
  pct,
  RRF_MAX,
  scoreFill,
  matchReason,
  siblingStats,
  strength,
} from "./format";
import { matchRoute } from "./router";

describe("format", () => {
  it("formats percentages and OCF", () => {
    expect(pct(0.1234)).toBe("12.3%");
    expect(ocf(0.06)).toBe("0.06%");
  });

  it("scales score bars on an absolute scale", () => {
    expect(scoreFill(0.75, "text")).toBeCloseTo(0.5);
    expect(scoreFill(1, "exposure")).toBe(1);
    expect(scoreFill(0.4, "text")).toBe(0.03);
    expect(scoreFill(RRF_MAX, "both")).toBe(1);
    expect(scoreFill(1 / 61, "both")).toBeCloseTo(0.5);
  });

  it("labels clusters", () => {
    expect(clusterLabel("trk_ftse100")).toBe("Tracker · FTSE 100");
    expect(clusterLabel("act_uk_income")).toBe("Near-dupe · UK Equity Income");
    expect(clusterLabel("act_new_thing")).toBe("Near-dupe · new thing");
    expect(clusterLabel(null)).toBeNull();
  });

  it("counts siblings found", () => {
    const hits = [{ cluster_id: "act_x" }, { cluster_id: null }, { cluster_id: "act_x" }];
    expect(siblingStats("act_x", clusterSize("act_x"), hits)).toEqual({ found: 2, total: 3 });
    expect(siblingStats("outlier_gold", clusterSize("outlier_gold"), hits)).toBeNull();
    expect(siblingStats(null, 0, hits)).toBeNull();
  });

  it("normalises intensities by max", () => {
    expect(intensities([0, 0.5, 0.25])).toEqual([0, 1, 0.5]);
    expect(intensities([0, 0])).toEqual([0, 0]);
  });
});

describe("plain language", () => {
  it("labels match strength", () => {
    expect(strength(0.8)).toBe("strong");
    expect(strength(0.66)).toBe("good");
    expect(strength(0.55)).toBe("weak");
  });

  it("explains fused matches", () => {
    expect(matchReason({ text: 2, exposure: 5 }, 10).label).toBe("Similar description and holdings");
    expect(matchReason({ text: null, exposure: 1 }, 10).label).toBe("Similar holdings");
    expect(matchReason({ text: 3, exposure: null }, 10).strength).toBe("good");
    // In both lists, but outside the top 10 of one of them: name the stronger method.
    const r = matchReason({ text: 4, exposure: 15 }, 10);
    expect(r.both).toBe(false);
    expect(r.label).toBe("Similar description");
    expect(matchReason({ text: 14, exposure: 18 }, 10).strength).toBe("weak");
  });
});

describe("api", () => {
  it("drops empty params from the query string", () => {
    expect(toQuery({ q: "gilts", limit: 5, exact: null, ia_sector: "" })).toBe("?q=gilts&limit=5");
    expect(toQuery({})).toBe("");
    expect(toQuery({ q: "x", ignore: ["a", "b"] })).toBe("?q=x&ignore=a&ignore=b");
  });
});

describe("router", () => {
  it("matches routes", () => {
    expect(matchRoute("/").name).toBe("search");
    const fund = matchRoute("/fund/F0042?mode=text");
    expect(fund).toMatchObject({ name: "fund", id: "F0042" });
    expect(matchRoute("/nope").name).toBe("notFound");
  });
});

describe("cheaperMatches", () => {
  it("keeps only cheaper matches, cheapest first, ties in match order", () => {
    const hits = [
      { id: "A", ocf: 0.5 },
      { id: "B", ocf: 0.1 },
      { id: "C", ocf: 0.3 },
      { id: "D", ocf: 0.1 },
      { id: "E", ocf: 0.4 },
    ];
    expect(cheaperMatches(hits, 0.4).map((h) => h.id)).toEqual(["B", "D", "C"]);
    expect(cheaperMatches(hits, 0.1)).toEqual([]);
  });
});
