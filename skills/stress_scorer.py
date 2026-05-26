"""
Composite financial stress scorer.

Input:
  indicators   — dict with current values for stress components:
                 hy_oas, ig_oas, ted_spread, vix, spread_2y10y
  percentiles  — dict loaded from data/processed/stress_percentiles.json
                 Each key maps to a sorted list of all historical non-null values.

Output:
  {
    stress_score:      float   — composite score 0–100
    stress_regime:     str     — "calm" | "watch" | "stress" | "crisis"
    component_scores:  dict    — per-component percentile scores before weighting
    components_used:   list    — which components contributed (some may be NULL)
  }

Component weights:
  hy_oas        30%  (higher OAS = more stress)
  ted_spread    20%  (higher spread = more stress)
  vix           20%  (higher VIX = more stress)
  ig_oas        15%  (higher OAS = more stress)
  spread_2y10y  15%  (INVERTED: lower / more negative = more stress)

Normalisation: percentile rank within the full non-null history for that component.
  For spread_2y10y: stress_contribution = 100 − percentile_rank
  (because a low/negative spread is the stressed state).

Weights are renormalised to sum to 100% when any component is NULL.
Regime thresholds: 0–25=calm, 25–50=watch, 50–75=stress, 75–100=crisis.

Percentiles file schema:
  {
    "hy_oas": [100.5, 120.3, ...],    # sorted ascending list of all historical values
    "ted_spread": [...],
    ...
  }
"""

import bisect
import json
import os
from functools import lru_cache

WEIGHTS = {
    "hy_oas":       0.30,
    "ted_spread":   0.20,
    "vix":          0.20,
    "ig_oas":       0.15,
    "spread_2y10y": 0.15,
}

REGIME_THRESHOLDS = [
    (75, "crisis"),
    (50, "stress"),
    (25, "watch"),
    (0,  "calm"),
]


@lru_cache(maxsize=1)
def _load_percentiles_from_file() -> dict:
    """Load stress_percentiles.json from data/processed/. Cached after first load."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(root, "data", "processed", "stress_percentiles.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"stress_percentiles.json not found at {path}. "
            "Run phase0/04_compute_columns.py first."
        )
    with open(path) as f:
        data = json.load(f)
    return data


def _percentile_rank(value: float, sorted_vals: list) -> float:
    """Percentile rank of value in a sorted list (0–100)."""
    if not sorted_vals:
        return 50.0
    pos = bisect.bisect_left(sorted_vals, value)
    return pos / len(sorted_vals) * 100


def _regime(score: float) -> str:
    for threshold, label in REGIME_THRESHOLDS:
        if score >= threshold:
            return label
    return "calm"


def score(indicators: dict, percentiles: dict = None) -> dict:
    """
    Compute composite stress score.

    Args:
        indicators:  dict with keys from WEIGHTS (missing or None = excluded).
        percentiles: pre-loaded percentile dict. If None, loads from file.

    Returns:
        dict with stress_score, stress_regime, component_scores, components_used.
    """
    if percentiles is None:
        percentiles = _load_percentiles_from_file()

    total_weight = 0.0
    weighted_sum = 0.0
    component_scores = {}
    components_used = []

    for comp, weight in WEIGHTS.items():
        value = indicators.get(comp)
        if value is None:
            continue
        sorted_vals = percentiles.get(comp)
        if not sorted_vals:
            continue

        pct = _percentile_rank(float(value), sorted_vals)

        # Invert spread_2y10y: lower spread (more negative) = more stress
        if comp == "spread_2y10y":
            pct = 100.0 - pct

        component_scores[comp] = round(pct, 2)
        weighted_sum += pct * weight
        total_weight += weight
        components_used.append(comp)

    if total_weight == 0:
        return {
            "stress_score": None,
            "stress_regime": None,
            "component_scores": {},
            "components_used": [],
        }

    # Renormalise weights so they always sum to 100%
    stress_score = round(weighted_sum / total_weight, 2)
    regime = _regime(stress_score)

    return {
        "stress_score":     stress_score,
        "stress_regime":    regime,
        "component_scores": component_scores,
        "components_used":  components_used,
    }
