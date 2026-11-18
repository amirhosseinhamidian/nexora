import { describe, expect, it } from "vitest";

import {
  formatExactPercent,
  performancePath,
  performancePlot,
  type PerformancePoint,
} from "./portfolio-analytics";

describe("portfolio performance presentation", () => {
  it("anchors sampling to the snapshot and requests a bounded window", () => {
    const url = new URL(
      performancePath("portfolio/one", "2026-11-19T12:00:00Z", "week"),
      "https://nexora.local",
    );
    expect(url.pathname).toBe("/api/v1/portfolios/portfolio%2Fone/performance");
    expect(url.searchParams.get("start_at")).toBe("2026-11-12T12:00:00.000Z");
    expect(url.searchParams.get("end_at")).toBe("2026-11-19T12:00:00Z");
    expect(url.searchParams.get("point_count")).toBe("8");
  });

  it("uses precise rates and leaves gaps between observed values", () => {
    const point: PerformancePoint = {
      as_of: "2026-11-19T12:00:00Z",
      cumulative_return: "0",
      external_flow: "0",
      nav: "400",
      state: "available",
      reason_code: null,
      period_return: null,
    };
    const plot = performancePlot(
      [
        point,
        { ...point, cumulative_return: "0.125", state: "stale" },
        { ...point, cumulative_return: null, state: "unavailable" },
        { ...point, cumulative_return: null, period_return: "0.2" },
      ],
      "en",
    );
    expect(plot?.samples[0]?.y).toBe(plot?.zeroY);
    expect(plot?.samples[1]?.stale).toBe(true);
    expect(plot?.samples.slice(2)).toEqual([undefined, undefined]);
    expect(plot?.maximum).toBe("12.50%");
    expect(formatExactPercent("-0.12345", "fa")).toBe("−۱۲٫۳۵٪");
  });
});
