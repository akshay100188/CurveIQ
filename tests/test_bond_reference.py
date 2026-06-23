"""Tests for the Python reference bond engine (textbook + analytic checks).

Run: python -m tests.test_bond_reference   (or pytest)
"""
from datetime import date

from pipeline.bond_reference import (Bond, compute, price_from_yield,
                                     yield_from_price, _days_30_360)


def _bond(coupon, settle, mat, dc="ACT/ACT", face=100.0, freq=2):
    return Bond(face, coupon, freq, dc, date.fromisoformat(settle), date.fromisoformat(mat))


def test_par_bond_yield_equals_coupon():
    # priced at par on a coupon date -> YTM == coupon rate
    b = _bond(0.06, "2020-01-15", "2030-01-15")
    assert abs(price_from_yield(b, 0.06)["clean_price"] - 100.0) < 1e-9
    assert abs(yield_from_price(b, 100.0) - 0.06) < 1e-8


def test_price_yield_roundtrip():
    b = _bond(0.035, "2021-03-15", "2029-09-15")
    for y in (0.01, 0.025, 0.05, 0.08, 0.12):
        p = price_from_yield(b, y)["clean_price"]
        assert abs(yield_from_price(b, p) - y) < 1e-6


def test_textbook_5pct_2y_at_6():
    # 5% semiannual, 2y, priced at 6% -> ~98.14
    b = _bond(0.05, "2020-01-15", "2022-01-15")
    assert abs(price_from_yield(b, 0.06)["clean_price"] - 98.1415) < 1e-3


def test_modified_duration_matches_numerical():
    # analytic modified duration ~= -(P(y+h)-P(y-h))/(2h*P)
    b = _bond(0.04, "2020-01-15", "2035-01-15")
    y, h = 0.045, 1e-5
    r = price_from_yield(b, y)
    p_up = price_from_yield(b, y + h)["dirty_price"]
    p_dn = price_from_yield(b, y - h)["dirty_price"]
    numerical = -(p_up - p_dn) / (2 * h * r["dirty_price"])
    assert abs(numerical - r["modified_duration"]) < 1e-3


def test_convexity_matches_numerical():
    b = _bond(0.04, "2020-01-15", "2035-01-15")
    y, h = 0.045, 1e-4
    r = price_from_yield(b, y)
    p0 = r["dirty_price"]
    p_up = price_from_yield(b, y + h)["dirty_price"]
    p_dn = price_from_yield(b, y - h)["dirty_price"]
    numerical = (p_up + p_dn - 2 * p0) / (p0 * h ** 2)
    assert abs(numerical - r["convexity"]) < 1e-1


def test_accrued_30_360_half_period():
    # settle exactly half a 30/360 period after issue -> accrued = half a coupon
    b = _bond(0.07, "2021-04-02", "2031-01-02", dc="30/360")
    r = price_from_yield(b, 0.07)
    # Jan2 -> Apr2 is 90 days (30/360); period Jan2->Jul2 is 180 -> 90/180 = 0.5
    assert abs(r["accrued_interest"] - (0.07 * 100 / 2) * 0.5) < 1e-9


def test_30_360_month_end_edge():
    # 31st handling: Jan 31 -> Feb 28 etc.
    assert _days_30_360(date(2021, 1, 31), date(2021, 7, 31)) == 180
    assert _days_30_360(date(2021, 1, 30), date(2021, 7, 31)) == 180


def test_dv01_ties_to_modified_duration():
    r = compute(100, 0.06, "2020-01-15", "2030-01-15", "US_TREASURY", ytm=0.06)
    assert abs(r["dv01"] - r["modified_duration"] * r["dirty_price"] * 1e-4) < 1e-12


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}")
    print(f"\n{len(fns)} bond reference tests passed")
