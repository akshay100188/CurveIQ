"""Tests for skills/stress_scorer.py"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skills.stress_scorer import score, _percentile_rank, _regime


# ---------------------------------------------------------------------------
# Shared fixtures — synthetic percentile lookup tables
# ---------------------------------------------------------------------------

def make_percentiles():
    """Synthetic sorted value arrays covering a useful range."""
    return {
        "hy_oas":       [float(x) for x in range(100, 2100, 4)],   # 100 to 2096
        "ted_spread":   [float(x) / 100 for x in range(10, 510)],  # 0.10 to 5.09
        "vix":          [float(x) / 2 for x in range(20, 200)],    # 10.0 to 99.5
        "ig_oas":       [float(x) for x in range(50, 800, 2)],     # 50 to 798
        "spread_2y10y": [float(x) / 100 for x in range(-200, 300)],# -2.00 to 2.99
    }


# ---------------------------------------------------------------------------
# Percentile rank helper
# ---------------------------------------------------------------------------

def test_percentile_rank_minimum():
    assert _percentile_rank(0.0, [1.0, 2.0, 3.0]) == 0.0


def test_percentile_rank_maximum():
    assert _percentile_rank(4.0, [1.0, 2.0, 3.0]) == 100.0


def test_percentile_rank_median():
    vals = [1.0, 2.0, 3.0, 4.0]  # 4 values
    # value 2.0 is at position 1 → rank = 1/4 * 100 = 25
    assert _percentile_rank(2.0, vals) == 25.0


def test_percentile_rank_empty_list():
    assert _percentile_rank(5.0, []) == 50.0


# ---------------------------------------------------------------------------
# Regime thresholds
# ---------------------------------------------------------------------------

def test_regime_calm():
    assert _regime(10.0) == "calm"
    assert _regime(24.9) == "calm"


def test_regime_watch():
    assert _regime(25.0) == "watch"
    assert _regime(49.9) == "watch"


def test_regime_stress():
    assert _regime(50.0) == "stress"
    assert _regime(74.9) == "stress"


def test_regime_crisis():
    assert _regime(75.0) == "crisis"
    assert _regime(99.9) == "crisis"


# ---------------------------------------------------------------------------
# Score output structure
# ---------------------------------------------------------------------------

def test_output_keys():
    pcts = make_percentiles()
    result = score({"hy_oas": 400, "vix": 20, "ted_spread": 0.5,
                    "ig_oas": 150, "spread_2y10y": 0.5}, pcts)
    assert set(result.keys()) == {
        "stress_score", "stress_regime", "component_scores", "components_used"
    }


def test_score_in_range():
    pcts = make_percentiles()
    result = score({"hy_oas": 400, "vix": 20, "ted_spread": 0.5,
                    "ig_oas": 150, "spread_2y10y": 0.5}, pcts)
    assert 0.0 <= result["stress_score"] <= 100.0


def test_all_components_used():
    pcts = make_percentiles()
    result = score({"hy_oas": 400, "vix": 20, "ted_spread": 0.5,
                    "ig_oas": 150, "spread_2y10y": 0.5}, pcts)
    assert len(result["components_used"]) == 5


# ---------------------------------------------------------------------------
# Directional correctness
# ---------------------------------------------------------------------------

def test_high_hy_oas_increases_score():
    pcts = make_percentiles()
    base = {"hy_oas": 300, "vix": 20, "ted_spread": 0.3, "ig_oas": 100, "spread_2y10y": 0.5}
    high = base.copy()
    high["hy_oas"] = 1800
    assert score(high, pcts)["stress_score"] > score(base, pcts)["stress_score"]


def test_high_vix_increases_score():
    pcts = make_percentiles()
    base = {"hy_oas": 400, "vix": 15, "ted_spread": 0.3, "ig_oas": 120, "spread_2y10y": 0.5}
    high = base.copy()
    high["vix"] = 85
    assert score(high, pcts)["stress_score"] > score(base, pcts)["stress_score"]


def test_negative_spread_increases_score():
    # Inverted curve = more stress (spread_2y10y component is inverted)
    pcts = make_percentiles()
    normal = {"hy_oas": 400, "vix": 20, "ted_spread": 0.5,
              "ig_oas": 150, "spread_2y10y": 1.0}   # steep normal
    inverted = normal.copy()
    inverted["spread_2y10y"] = -1.0                  # inverted
    assert score(inverted, pcts)["stress_score"] > score(normal, pcts)["stress_score"]


def test_all_low_values_gives_calm_regime():
    pcts = make_percentiles()
    # All near minimum
    calm_indicators = {
        "hy_oas": 110,      # near bottom of range
        "vix": 11,
        "ted_spread": 0.12,
        "ig_oas": 55,
        "spread_2y10y": 2.5,  # steep normal → low stress
    }
    result = score(calm_indicators, pcts)
    assert result["stress_regime"] in ("calm", "watch")


def test_all_high_values_gives_crisis_regime():
    pcts = make_percentiles()
    # All near maximum
    crisis_indicators = {
        "hy_oas": 2000,     # near top of range
        "vix": 95,
        "ted_spread": 4.5,
        "ig_oas": 790,
        "spread_2y10y": -1.8,  # deeply inverted
    }
    result = score(crisis_indicators, pcts)
    assert result["stress_regime"] in ("stress", "crisis")


# ---------------------------------------------------------------------------
# NULL handling and weight renormalisation
# ---------------------------------------------------------------------------

def test_missing_component_still_returns_score():
    pcts = make_percentiles()
    # Only 3 of 5 components provided
    result = score({"hy_oas": 400, "vix": 25, "ted_spread": 0.5}, pcts)
    assert result["stress_score"] is not None
    assert len(result["components_used"]) == 3


def test_no_components_returns_none():
    pcts = make_percentiles()
    result = score({}, pcts)
    assert result["stress_score"] is None
    assert result["stress_regime"] is None


def test_none_values_excluded():
    pcts = make_percentiles()
    result = score({"hy_oas": None, "vix": 25, "ted_spread": None,
                    "ig_oas": None, "spread_2y10y": None}, pcts)
    assert result["stress_score"] is not None
    assert result["components_used"] == ["vix"]


def test_weight_renormalisation_consistency():
    # Score with all 5 components at mid-range should ≈ score with 3 components at same percentile
    # because weights renormalise — any uniform mid-range input → ~50 score
    pcts = make_percentiles()
    # Pick values that land at ~50th percentile of each series
    mid = {
        "hy_oas":       1050.0,   # mid of 100–2096
        "vix":          54.75,    # mid of 10–99.5
        "ted_spread":   2.595,    # mid of 0.10–5.09
        "ig_oas":       424.0,    # mid of 50–798
        "spread_2y10y": 0.495,    # mid of -2.00 to 2.99  (spread_2y10y inverted)
    }
    result_all = score(mid, pcts)
    result_three = score(
        {"hy_oas": mid["hy_oas"], "vix": mid["vix"], "ted_spread": mid["ted_spread"]},
        pcts
    )
    # Both should be near 50; renormalisation keeps them in same ballpark
    assert abs(result_all["stress_score"] - result_three["stress_score"]) < 10.0
