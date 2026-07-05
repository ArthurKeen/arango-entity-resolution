import { describe, it, expect } from "vitest";
import { reviewCsvUrl } from "./review";

describe("reviewCsvUrl", () => {
  it("builds a plain URL with no filters", () => {
    expect(reviewCsvUrl("customers")).toBe("/api/review/customers/export.csv");
  });

  it("includes filter params but omits pagination", () => {
    const url = reviewCsvUrl("customers", {
      status: "match",
      min_score: 0.7,
      limit: 10,
      offset: 20,
    });
    expect(url).toContain("/api/review/customers/export.csv?");
    expect(url).toContain("status=match");
    expect(url).toContain("min_score=0.7");
    expect(url).not.toContain("limit");
    expect(url).not.toContain("offset");
  });
});
