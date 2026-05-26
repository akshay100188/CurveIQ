"""
Yield curve shape classifier.

Input:  dict of tenor yields keyed by t1m, t3m, t6m, t1y, t2y, t3y,
        t5y, t7y, t10y, t20y, t30y  (values in percent, e.g. 4.85)
Output: {
    shape:               str   — "normal" | "inverted" | "flat" | "humped"
    steepness_score:     float — spread_2y10y in percent (signed)
    inversion_flag:      bool
    inversion_depth_bps: float — abs(spread_2y10y) * 100 if inverted, else 0
}

Classification rules:
  inverted → spread_2y10y < 0   (t2y > t10y)
  flat     → |spread_2y10y| <= 0.15
  humped   → t3y or t5y is the maximum value across all available tenors
  normal   → spread_2y10y > 0.15 and no humped condition

Returns None for shape if t2y or t10y is missing.
"""

TENOR_ORDER = ["t1m", "t3m", "t6m", "t1y", "t2y", "t3y", "t5y", "t7y", "t10y", "t20y", "t30y"]

FLAT_THRESHOLD = 0.15   # percent — spreads within this band are "flat"
HUMPED_TENORS = {"t3y", "t5y"}


def classify(yields: dict) -> dict:
    """
    Classify the yield curve shape from a tenor yield dict.

    Args:
        yields: dict with tenor keys (t1m … t30y) mapped to float yield values
                in percent. Missing or None values are ignored.

    Returns:
        dict with shape, steepness_score, inversion_flag, inversion_depth_bps.
        shape is None if t2y or t10y is missing.
    """
    t2y = yields.get("t2y")
    t10y = yields.get("t10y")

    if t2y is None or t10y is None:
        return {
            "shape": None,
            "steepness_score": None,
            "inversion_flag": None,
            "inversion_depth_bps": None,
        }

    t2y = float(t2y)
    t10y = float(t10y)
    spread = round(t10y - t2y, 6)

    # Determine shape
    if spread < 0:
        shape = "inverted"
    elif abs(spread) <= FLAT_THRESHOLD:
        shape = "flat"
    else:
        # Check humped: t3y or t5y is the global maximum
        valid = {k: float(v) for k, v in yields.items()
                 if k in TENOR_ORDER and v is not None}
        if valid:
            peak_tenor = max(valid, key=valid.get)
            shape = "humped" if peak_tenor in HUMPED_TENORS else "normal"
        else:
            shape = "normal"

    inversion_flag = spread < 0
    inversion_depth_bps = round(abs(spread) * 100, 4) if inversion_flag else 0.0

    return {
        "shape": shape,
        "steepness_score": round(spread, 6),
        "inversion_flag": inversion_flag,
        "inversion_depth_bps": inversion_depth_bps,
    }
