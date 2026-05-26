"""Tests for skills/curve_classifier.py"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skills.curve_classifier import classify


# ---------------------------------------------------------------------------
# Shape classification
# ---------------------------------------------------------------------------

def test_normal_curve():
    yields = {"t3m": 4.0, "t2y": 4.2, "t5y": 4.5, "t10y": 4.8, "t30y": 5.0}
    result = classify(yields)
    assert result["shape"] == "normal"
    assert result["inversion_flag"] is False
    assert result["inversion_depth_bps"] == 0.0
    assert result["steepness_score"] > 0


def test_inverted_curve():
    yields = {"t3m": 5.5, "t2y": 5.1, "t10y": 4.5, "t30y": 4.3}
    result = classify(yields)
    assert result["shape"] == "inverted"
    assert result["inversion_flag"] is True
    assert result["inversion_depth_bps"] > 0
    assert result["steepness_score"] < 0


def test_flat_curve_positive_spread():
    # spread = 0.10 — within flat threshold (0.15)
    yields = {"t2y": 4.80, "t10y": 4.90}
    result = classify(yields)
    assert result["shape"] == "flat"
    assert result["inversion_flag"] is False


def test_flat_curve_negative_spread_within_threshold():
    # spread = -0.10 — within flat threshold magnitude? No — flat requires abs <= 0.15
    # but inverted requires spread < 0. Inverted takes priority.
    yields = {"t2y": 4.90, "t10y": 4.80}
    result = classify(yields)
    # spread = -0.10; abs(spread) = 0.10 <= 0.15 BUT spread < 0 → inverted rule fires first
    assert result["shape"] == "inverted"


def test_flat_curve_exact_threshold():
    # spread = exactly 0.15 — should be flat
    yields = {"t2y": 4.00, "t10y": 4.15}
    result = classify(yields)
    assert result["shape"] == "flat"


def test_flat_curve_just_above_threshold():
    # spread = 0.16 — just above flat threshold → normal
    yields = {"t2y": 4.00, "t10y": 4.16, "t3y": 4.08, "t5y": 4.12}
    result = classify(yields)
    assert result["shape"] == "normal"


def test_humped_curve_peak_at_t3y():
    yields = {"t1m": 3.5, "t3m": 4.0, "t2y": 4.2, "t3y": 5.0,
              "t5y": 4.8, "t10y": 4.5, "t30y": 4.2}
    result = classify(yields)
    assert result["shape"] == "humped"


def test_humped_curve_peak_at_t5y():
    yields = {"t2y": 4.0, "t3y": 4.4, "t5y": 5.1, "t7y": 4.9,
              "t10y": 4.5, "t30y": 4.1}
    result = classify(yields)
    assert result["shape"] == "humped"


def test_not_humped_when_peak_at_t10y():
    # Peak at t10y — should be normal (assuming spread > 0.15)
    yields = {"t2y": 3.5, "t3y": 3.8, "t5y": 4.0, "t10y": 4.8, "t30y": 4.6}
    result = classify(yields)
    assert result["shape"] == "normal"


# ---------------------------------------------------------------------------
# Steepness score
# ---------------------------------------------------------------------------

def test_steepness_score_is_spread_2y10y():
    yields = {"t2y": 4.0, "t10y": 4.75}
    result = classify(yields)
    assert abs(result["steepness_score"] - 0.75) < 1e-5


def test_inversion_depth_bps():
    # spread = -0.50 percent → 50 bps
    yields = {"t2y": 5.0, "t10y": 4.5}
    result = classify(yields)
    assert result["inversion_flag"] is True
    assert abs(result["inversion_depth_bps"] - 50.0) < 0.01


# ---------------------------------------------------------------------------
# Missing data handling
# ---------------------------------------------------------------------------

def test_missing_t2y_returns_none_shape():
    yields = {"t10y": 4.5}
    result = classify(yields)
    assert result["shape"] is None
    assert result["inversion_flag"] is None


def test_missing_t10y_returns_none_shape():
    yields = {"t2y": 4.5}
    result = classify(yields)
    assert result["shape"] is None


def test_empty_dict_returns_none_shape():
    result = classify({})
    assert result["shape"] is None


def test_none_values_treated_as_missing():
    yields = {"t2y": None, "t10y": 4.5}
    result = classify(yields)
    assert result["shape"] is None


# ---------------------------------------------------------------------------
# Historical spot checks
# ---------------------------------------------------------------------------

def test_2023_deep_inversion():
    # 2023-03-01 approximate values: 2Y ~4.89, 10Y ~3.96
    yields = {"t2y": 4.89, "t10y": 3.96}
    result = classify(yields)
    assert result["shape"] == "inverted"
    assert result["inversion_depth_bps"] > 80   # ~93 bps inversion


def test_2006_normal_pre_inversion():
    # 2006-01: 2Y ~4.35, 10Y ~4.42 — normal but nearly flat
    yields = {"t2y": 4.35, "t10y": 4.42}
    result = classify(yields)
    assert result["shape"] == "flat"   # spread = 0.07 < 0.15


def test_2004_normal_steep():
    # 2004-01: 2Y ~1.87, 10Y ~4.15 — steep normal
    yields = {"t2y": 1.87, "t10y": 4.15}
    result = classify(yields)
    assert result["shape"] == "normal"
    assert result["steepness_score"] > 2.0
