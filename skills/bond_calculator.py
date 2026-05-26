"""
Bond risk metric calculator — semi-annual compounding convention.

Two operating modes (mutually exclusive):
  MODE A — Price from YTM:  provide face_value, coupon_rate, maturity_years, ytm
  MODE B — YTM from Price:  provide face_value, coupon_rate, maturity_years, price

Input values:
  face_value     — par value in dollars (e.g. 1000.0)
  coupon_rate    — annual coupon as decimal (e.g. 0.05 for 5%)
  maturity_years — years to maturity (e.g. 10.0)
  ytm            — annual yield to maturity as decimal (e.g. 0.045)  [MODE A]
  price          — market price in dollars (e.g. 950.0)              [MODE B]

Output:
  {
    price:             float  — clean price in dollars
    ytm:               float  — annual YTM as decimal
    duration:          float  — Macaulay duration in years
    modified_duration: float  — modified duration
    convexity:         float  — convexity (semi-annual convention)
    dv01:              float  — dollar value of 1 basis point
  }

All outputs rounded to 6 decimal places.
Semi-annual compounding throughout: n_periods = maturity_years * 2,
  period_rate = ytm / 2, period_coupon = face_value * coupon_rate / 2.
YTM solving uses scipy.optimize.brentq — bracket [0.0001, 0.9999].
"""

from scipy.optimize import brentq


def _price_from_ytm(face_value: float, coupon_rate: float,
                    maturity_years: float, ytm: float) -> float:
    """Compute bond price given YTM. Semi-annual compounding."""
    n = int(round(maturity_years * 2))
    c = face_value * coupon_rate / 2      # semi-annual coupon payment
    r = ytm / 2                           # semi-annual yield

    if r == 0:
        return c * n + face_value

    coupon_pv = c * (1 - (1 + r) ** (-n)) / r
    par_pv = face_value / (1 + r) ** n
    return coupon_pv + par_pv


def _ytm_from_price(face_value: float, coupon_rate: float,
                    maturity_years: float, price: float) -> float:
    """Solve for YTM given market price using brentq. Semi-annual compounding."""
    def objective(ytm_guess):
        return _price_from_ytm(face_value, coupon_rate, maturity_years, ytm_guess) - price

    # brentq requires sign change across the bracket
    ytm = brentq(objective, 0.0001, 0.9999, xtol=1e-10, maxiter=1000)
    return ytm


def _duration_convexity(face_value: float, coupon_rate: float,
                        maturity_years: float, ytm: float,
                        price: float) -> tuple:
    """
    Compute Macaulay duration, modified duration, and convexity.
    Returns (duration, modified_duration, convexity).
    """
    n = int(round(maturity_years * 2))
    c = face_value * coupon_rate / 2
    r = ytm / 2

    duration_num = 0.0
    convexity_num = 0.0

    for t in range(1, n + 1):
        cash_flow = c if t < n else c + face_value
        pv_cf = cash_flow / (1 + r) ** t
        # Macaulay duration: weight by time in periods
        duration_num += t * pv_cf
        # Convexity: t*(t+1) weighting
        convexity_num += t * (t + 1) * pv_cf

    # Convert periods to years for Macaulay duration
    macaulay_duration = (duration_num / price) / 2
    modified_duration = macaulay_duration / (1 + r)

    # Semi-annual convexity formula — convert to annual
    convexity = (convexity_num / price) / ((1 + r) ** 2) / 4

    return macaulay_duration, modified_duration, convexity


def calculate(face_value: float, coupon_rate: float, maturity_years: float,
              ytm: float = None, price: float = None) -> dict:
    """
    Compute full bond risk metrics.

    Provide exactly one of ytm or price; the other is derived.

    Args:
        face_value:     Par value in dollars.
        coupon_rate:    Annual coupon rate as decimal.
        maturity_years: Years to maturity.
        ytm:            Annual yield to maturity as decimal (MODE A).
        price:          Market price in dollars (MODE B).

    Returns:
        dict with price, ytm, duration, modified_duration, convexity, dv01.

    Raises:
        ValueError: if both or neither of ytm/price are provided, or
                    if inputs are out of valid range.
    """
    if ytm is None and price is None:
        raise ValueError("Provide exactly one of ytm or price.")
    if ytm is not None and price is not None:
        raise ValueError("Provide exactly one of ytm or price, not both.")

    if face_value <= 0:
        raise ValueError(f"face_value must be positive, got {face_value}")
    if coupon_rate < 0 or coupon_rate > 1:
        raise ValueError(f"coupon_rate must be in [0, 1], got {coupon_rate}")
    if maturity_years <= 0:
        raise ValueError(f"maturity_years must be positive, got {maturity_years}")

    if ytm is not None:
        if not (0 < ytm < 1):
            raise ValueError(f"ytm must be in (0, 1), got {ytm}")
        computed_price = _price_from_ytm(face_value, coupon_rate, maturity_years, ytm)
        computed_ytm = ytm
    else:
        if price <= 0:
            raise ValueError(f"price must be positive, got {price}")
        computed_ytm = _ytm_from_price(face_value, coupon_rate, maturity_years, price)
        computed_price = price

    duration, modified_duration, convexity = _duration_convexity(
        face_value, coupon_rate, maturity_years, computed_ytm, computed_price
    )

    dv01 = modified_duration * computed_price * 0.0001

    return {
        "price":             round(computed_price,    6),
        "ytm":               round(computed_ytm,      6),
        "duration":          round(duration,           6),
        "modified_duration": round(modified_duration,  6),
        "convexity":         round(convexity,          6),
        "dv01":              round(dv01,               6),
    }
