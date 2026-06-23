"""Reference single-bond pricing engine (Python twin of frontend/lib/bond.ts).

This is the canonical, tested implementation of the bond math. It is NOT used at
runtime by the app (the calculator runs client-side in TypeScript) — it exists so
the TS engine can be checked for parity against an independent implementation via
shared golden vectors (see scripts at bottom / tests/test_bond_reference.py).

Conventions:
  - US Treasury : semi-annual, ACT/ACT (ICMA) day-count.
  - India G-Sec : semi-annual, 30/360 day-count (RBI G-Sec primer + FIMMDA).

Pricing uses the standard street formula with a within-period settlement fraction
w = (days settlement->next coupon) / (days in the coupon period):

    dirty = Σ_{k=0..n-1}  CF_k / (1+i)^(w+k)        i = ytm / frequency
    accrued = coupon * (1 - w)
    clean   = dirty - accrued
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import date


# --- day-count -------------------------------------------------------------
def _days_30_360(d1: date, d2: date) -> int:
    """US (NASD) 30/360 bond basis with month-end edge handling."""
    y1, m1, day1 = d1.year, d1.month, d1.day
    y2, m2, day2 = d2.year, d2.month, d2.day
    if day1 == 31:
        day1 = 30
    if day2 == 31 and day1 == 30:
        day2 = 30
    return (y2 - y1) * 360 + (m2 - m1) * 30 + (day2 - day1)


def _day_count(d1: date, d2: date, convention: str) -> int:
    if convention == "30/360":
        return _days_30_360(d1, d2)
    return (d2 - d1).days          # ACT/ACT (ICMA): actual days


# --- date helpers ----------------------------------------------------------
def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    # clamp day to month length
    from calendar import monthrange
    day = min(d.day, monthrange(y, m)[1])
    return date(y, m, day)


def _schedule(settle: date, maturity: date, freq: int):
    """Return (prev_coupon, next_coupon, [remaining coupon dates ascending])."""
    step = 12 // freq
    cursor = maturity
    after = []
    while cursor > settle:
        after.append(cursor)
        cursor = _add_months(cursor, -step)
    prev = cursor                       # first coupon date <= settle
    after.reverse()                     # ascending, all strictly > settle
    return prev, after[0], after


# --- core engine -----------------------------------------------------------
@dataclass
class Bond:
    face_value: float
    coupon_rate: float       # annual, decimal (0.06 == 6%)
    frequency: int           # coupons per year
    day_count: str           # 'ACT/ACT' | '30/360'
    settlement: date
    maturity: date


def _w_and_n(b: Bond):
    prev, nxt, remaining = _schedule(b.settlement, b.maturity, b.frequency)
    period = _day_count(prev, nxt, b.day_count)
    accrued_days = _day_count(prev, b.settlement, b.day_count)
    w = (period - accrued_days) / period
    return w, len(remaining), accrued_days, period


def price_from_yield(b: Bond, ytm: float) -> dict:
    i = ytm / b.frequency
    cpn = b.face_value * b.coupon_rate / b.frequency
    w, n, accrued_days, period = _w_and_n(b)
    dirty = 0.0
    mac_num = 0.0
    conv_num = 0.0
    for k in range(n):
        t = w + k                                  # periods to cashflow
        cf = cpn + (b.face_value if k == n - 1 else 0.0)
        pv = cf / (1 + i) ** t
        dirty += pv
        mac_num += (t / b.frequency) * pv          # time in years * pv
        conv_num += pv * t * (t + 1)
    accrued = cpn * (accrued_days / period)
    clean = dirty - accrued
    macaulay = mac_num / dirty
    modified = macaulay / (1 + i)
    convexity = conv_num / (dirty * (1 + i) ** 2 * b.frequency ** 2)
    dv01 = modified * dirty * 1e-4
    current_yield = (b.coupon_rate * b.face_value) / clean if clean else None
    return {
        "dirty_price": dirty, "clean_price": clean, "accrued_interest": accrued,
        "current_yield": current_yield, "macaulay_duration": macaulay,
        "modified_duration": modified, "convexity": convexity, "dv01": dv01,
        "yield": ytm,
    }


def yield_from_price(b: Bond, clean_price: float) -> float:
    """Solve YTM from clean price. Newton–Raphson with bisection fallback."""
    w, n, accrued_days, period = _w_and_n(b)
    cpn = b.face_value * b.coupon_rate / b.frequency
    target_dirty = clean_price + cpn * (accrued_days / period)

    def dirty_at(y: float) -> float:
        i = y / b.frequency
        return sum((cpn + (b.face_value if k == n - 1 else 0.0)) / (1 + i) ** (w + k)
                   for k in range(n))

    # Newton–Raphson seeded at current yield
    y = max(0.0001, b.coupon_rate)
    for _ in range(100):
        r = price_from_yield(b, y)
        f = r["dirty_price"] - target_dirty
        if abs(f) < 1e-10:
            return y
        deriv = -r["modified_duration"] * r["dirty_price"]   # dPrice/dy
        if deriv == 0:
            break
        step = f / deriv
        y_new = y - step
        if y_new <= 0 or y_new > 2:
            break
        y = y_new
    # bisection fallback over a wide bracket
    lo, hi = 1e-6, 2.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if dirty_at(mid) - target_dirty > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


PRESETS = {
    "US_TREASURY": {"frequency": 2, "day_count": "ACT/ACT"},
    "INDIA_GSEC": {"frequency": 2, "day_count": "30/360"},
}


def compute(face, coupon_rate, settlement, maturity, preset="US_TREASURY",
            price=None, ytm=None) -> dict:
    p = PRESETS[preset]
    b = Bond(face, coupon_rate, p["frequency"], p["day_count"],
             date.fromisoformat(settlement), date.fromisoformat(maturity))
    if ytm is None:
        ytm = yield_from_price(b, price)
    return price_from_yield(b, ytm)


# --- golden-vector generator (shared parity fixture for TS + Python tests) --
GOLDEN_CASES = [
    {"name": "us_par_6pct_10y", "face": 100, "coupon_rate": 0.06,
     "settlement": "2020-01-15", "maturity": "2030-01-15", "preset": "US_TREASURY", "ytm": 0.06},
    {"name": "us_5pct_2y_at_6", "face": 100, "coupon_rate": 0.05,
     "settlement": "2020-01-15", "maturity": "2022-01-15", "preset": "US_TREASURY", "ytm": 0.06},
    {"name": "us_3pct_30y_at_4_midperiod", "face": 100, "coupon_rate": 0.03,
     "settlement": "2021-04-15", "maturity": "2051-01-15", "preset": "US_TREASURY", "ytm": 0.04},
    {"name": "india_gsec_7pct_10y_30360", "face": 100, "coupon_rate": 0.07,
     "settlement": "2021-04-15", "maturity": "2031-01-02", "preset": "INDIA_GSEC", "ytm": 0.0725},
]


def build_golden() -> list[dict]:
    out = []
    for c in GOLDEN_CASES:
        r = compute(c["face"], c["coupon_rate"], c["settlement"], c["maturity"],
                    c["preset"], ytm=c["ytm"])
        out.append({"case": c, "expected": {k: r[k] for k in
                   ("dirty_price", "clean_price", "accrued_interest", "current_yield",
                    "macaulay_duration", "modified_duration", "convexity", "dv01")}})
    return out


if __name__ == "__main__":
    import pathlib
    golden = build_golden()
    dest = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "lib" / "bond.golden.json"
    dest.write_text(json.dumps(golden, indent=2))
    print(f"wrote {len(golden)} golden vectors -> {dest}")
    for g in golden:
        e = g["expected"]
        print(f"  {g['case']['name']:32} clean={e['clean_price']:.4f} "
              f"modD={e['modified_duration']:.4f} conv={e['convexity']:.4f} dv01={e['dv01']:.5f}")
