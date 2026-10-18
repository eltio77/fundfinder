import { describe, expect, it } from "vitest";

import { toQuery } from "./api";
import {
  clusterLabel,
  clusterSize,
  intensities,
  ocf,
  pct,
  RRF_MAX,
  scoreFill,
  siblingStats,
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
    expect(clusterLabel("trk_ftse100")).toBe("Tracker · ftse100");
    expect(clusterLabel("act_uk_income")).toBe("Near-dupe · uk income");
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

describe("api", () => {
  it("drops empty params from the query string", () => {
    expect(toQuery({ q: "gilts", limit: 5, exact: null, ia_sector: "" })).toBe("?q=gilts&limit=5");
    expect(toQuery({})).toBe("");
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
