import { describe, expect, it } from "vitest";
import golden from "./bond.golden.json";
import { compute, priceFromYield, yieldFromPrice, type Bond } from "./bond";

const bond = (couponRate: number, settlement: string, maturity: string,
              dayCount: "ACT/ACT" | "30/360" = "ACT/ACT"): Bond => ({
  faceValue: 100, couponRate, frequency: 2, dayCount,
  settlement: new Date(settlement + "T00:00:00Z"),
  maturity: new Date(maturity + "T00:00:00Z"),
});

describe("bond engine — textbook", () => {
  it("par bond priced at par yields its coupon", () => {
    const b = bond(0.06, "2020-01-15", "2030-01-15");
    expect(priceFromYield(b, 0.06).cleanPrice).toBeCloseTo(100, 9);
    expect(yieldFromPrice(b, 100)).toBeCloseTo(0.06, 8);
  });

  it("5% 2y bond priced at 6% ~= 98.14", () => {
    expect(priceFromYield(bond(0.05, "2020-01-15", "2022-01-15"), 0.06).cleanPrice)
      .toBeCloseTo(98.1415, 3);
  });

  it("price<->yield round-trips to <1e-6", () => {
    const b = bond(0.035, "2021-03-15", "2029-09-15");
    for (const y of [0.01, 0.025, 0.05, 0.08, 0.12]) {
      const p = priceFromYield(b, y).cleanPrice;
      expect(yieldFromPrice(b, p)).toBeCloseTo(y, 6);
    }
  });

  it("modified duration matches a numerical derivative", () => {
    const b = bond(0.04, "2020-01-15", "2035-01-15");
    const y = 0.045, h = 1e-5;
    const r = priceFromYield(b, y);
    const up = priceFromYield(b, y + h).dirtyPrice;
    const dn = priceFromYield(b, y - h).dirtyPrice;
    const numerical = -(up - dn) / (2 * h * r.dirtyPrice);
    expect(numerical).toBeCloseTo(r.modifiedDuration, 3);
  });

  it("30/360 half-period accrual = half a coupon", () => {
    const r = priceFromYield(bond(0.07, "2021-04-02", "2031-01-02", "30/360"), 0.07);
    expect(r.accruedInterest).toBeCloseTo((0.07 * 100 / 2) * 0.5, 9);
  });
});

describe("bond engine — parity with Python reference (golden vectors)", () => {
  for (const g of golden as any[]) {
    it(`matches Python: ${g.case.name}`, () => {
      const r = compute({
        faceValue: g.case.face, couponRate: g.case.coupon_rate,
        settlement: g.case.settlement, maturity: g.case.maturity,
        preset: g.case.preset, ytm: g.case.ytm,
      });
      const e = g.expected;
      expect(r.cleanPrice).toBeCloseTo(e.clean_price, 8);
      expect(r.dirtyPrice).toBeCloseTo(e.dirty_price, 8);
      expect(r.accruedInterest).toBeCloseTo(e.accrued_interest, 8);
      expect(r.macaulayDuration).toBeCloseTo(e.macaulay_duration, 8);
      expect(r.modifiedDuration).toBeCloseTo(e.modified_duration, 8);
      expect(r.convexity).toBeCloseTo(e.convexity, 6);
      expect(r.dv01).toBeCloseTo(e.dv01, 8);
    });
  }
});
