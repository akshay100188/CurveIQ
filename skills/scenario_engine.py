"""
Rate shock scenario engine — convexity-adjusted price impact.

Input:
  bond_metrics  — output dict from skills/bond_calculator.calculate()
  shocks_bps    — list of rate shocks in basis points
                  (default: [-200, -100, -50, +50, +100, +200])

Output:
  list of dicts, one per shock:
  {
    shock_bps:        int   — the shock applied (e.g. -100)
    price_change_pct: float — price change in percent (e.g. -6.82 for a 6.82% drop)
    dollar_impact:    float — dollar gain/loss on the face value
    new_price:        float — estimated price after shock
    new_ytm:          float — new YTM after shock (as decimal)
  }

Formula (convexity-adjusted, standard bond math):
  shock_decimal = shock_bps / 10_000
  price_change_pct = (-modified_duration * shock_decimal
                      + 0.5 * convexity * shock_decimal**2) * 100

Units are explicit throughout:
  price_change_pct  — percentage (e.g. -6.82 means −6.82%)
  dollar_impact     — face_value * price_change_pct / 100
  new_price         — price * (1 + price_change_pct / 100)
  new_ytm           — ytm + shock_decimal  (linear approximation)
"""

DEFAULT_SHOCKS_BPS = [-200, -100, -50, 50, 100, 200]


def run(bond_metrics: dict, shocks_bps: list = None) -> list:
    """
    Compute convexity-adjusted price impact for a list of rate shocks.

    Args:
        bond_metrics: Output from skills/bond_calculator.calculate().
                      Must contain: price, ytm, modified_duration, convexity.
                      face_value is inferred as price if not present (use
                      the face_value from the original bond_calculator call).
        shocks_bps:   List of integer basis point shocks. Defaults to
                      [-200, -100, -50, +50, +100, +200].

    Returns:
        List of scenario dicts ordered by shock_bps ascending.
    """
    if shocks_bps is None:
        shocks_bps = DEFAULT_SHOCKS_BPS

    price = float(bond_metrics["price"])
    ytm = float(bond_metrics["ytm"])
    mod_dur = float(bond_metrics["modified_duration"])
    convexity = float(bond_metrics["convexity"])

    # face_value is needed for dollar_impact.
    # bond_metrics from bond_calculator doesn't store face_value directly,
    # so callers should pass it via bond_metrics["face_value"] if available.
    # Default to price (as if face_value == current price) when not provided.
    face_value = float(bond_metrics.get("face_value", price))

    results = []
    for shock_bps in sorted(shocks_bps):
        shock = shock_bps / 10_000          # convert bps to decimal

        # Convexity-adjusted price change (result is a decimal fraction)
        price_change_fraction = (-mod_dur * shock) + (0.5 * convexity * shock ** 2)
        price_change_pct = round(price_change_fraction * 100, 6)

        dollar_impact = round(face_value * price_change_pct / 100, 4)
        new_price = round(price * (1 + price_change_pct / 100), 6)
        new_ytm = round(ytm + shock, 6)

        results.append({
            "shock_bps":        shock_bps,
            "price_change_pct": price_change_pct,
            "dollar_impact":    dollar_impact,
            "new_price":        new_price,
            "new_ytm":          new_ytm,
        })

    return results
