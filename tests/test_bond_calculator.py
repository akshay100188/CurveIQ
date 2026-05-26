"""Tests for skills/bond_calculator.py"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skills.bond_calculator import calculate


# ---------------------------------------------------------------------------
# MODE A: Price from YTM
# ---------------------------------------------------------------------------

def test_par_bond_price():
    # Coupon == YTM → price == face value (par bond)
    result = calculate(face_value=1000, coupon_rate=0.05, maturity_years=10, ytm=0.05)
    assert abs(result["price"] - 1000.0) < 0.01


def test_discount_bond():
    # YTM > coupon → price < face value
    result = calculate(face_value=1000, coupon_rate=0.04, maturity_years=10, ytm=0.06)
    assert result["price"] < 1000.0


def test_premium_bond():
    # YTM < coupon → price > face value
    result = calculate(face_value=1000, coupon_rate=0.06, maturity_years=10, ytm=0.04)
    assert result["price"] > 1000.0


def test_known_bond_price():
    # 5% coupon, 10yr, YTM=4%, semi-annual compounding.
    # 25 * [1-(1.02)^-20]/0.02 + 1000/(1.02)^20 = 1081.757
    # (Annual-compounding tables give 1081.11 — different convention.)
    result = calculate(face_value=1000, coupon_rate=0.05, maturity_years=10, ytm=0.04)
    assert abs(result["price"] - 1081.757) < 0.01


def test_zero_coupon_bond():
    # Zero-coupon: price = face / (1 + ytm/2)^(2*n)
    result = calculate(face_value=1000, coupon_rate=0.0, maturity_years=5, ytm=0.06)
    expected = 1000 / (1 + 0.03) ** 10
    assert abs(result["price"] - expected) < 0.01


# ---------------------------------------------------------------------------
# MODE B: YTM from Price
# ---------------------------------------------------------------------------

def test_ytm_from_par_price():
    # Price = face value → YTM = coupon rate
    result = calculate(face_value=1000, coupon_rate=0.05, maturity_years=10, price=1000.0)
    assert abs(result["ytm"] - 0.05) < 1e-5


def test_ytm_from_discount_price():
    # Price below par → YTM > coupon rate
    result = calculate(face_value=1000, coupon_rate=0.04, maturity_years=10, price=900.0)
    assert result["ytm"] > 0.04


def test_ytm_from_premium_price():
    # Price above par → YTM < coupon rate
    result = calculate(face_value=1000, coupon_rate=0.06, maturity_years=10, price=1100.0)
    assert result["ytm"] < 0.06


def test_mode_b_round_trips_mode_a():
    # Round-trip: price_from_ytm(ytm) → ytm_from_price(price) == original ytm
    original_ytm = 0.0425
    result_a = calculate(face_value=1000, coupon_rate=0.05, maturity_years=7, ytm=original_ytm)
    result_b = calculate(face_value=1000, coupon_rate=0.05, maturity_years=7, price=result_a["price"])
    assert abs(result_b["ytm"] - original_ytm) < 1e-6


# ---------------------------------------------------------------------------
# Duration properties
# ---------------------------------------------------------------------------

def test_duration_positive():
    result = calculate(face_value=1000, coupon_rate=0.05, maturity_years=10, ytm=0.05)
    assert result["duration"] > 0
    assert result["modified_duration"] > 0


def test_modified_duration_less_than_macaulay():
    # Modified duration < Macaulay duration (divided by 1 + ytm/2)
    result = calculate(face_value=1000, coupon_rate=0.05, maturity_years=10, ytm=0.05)
    assert result["modified_duration"] < result["duration"]


def test_longer_maturity_higher_duration():
    short = calculate(face_value=1000, coupon_rate=0.05, maturity_years=5, ytm=0.05)
    long_ = calculate(face_value=1000, coupon_rate=0.05, maturity_years=20, ytm=0.05)
    assert long_["duration"] > short["duration"]


def test_zero_coupon_duration_equals_maturity():
    # Zero-coupon bond: Macaulay duration == maturity (by definition)
    result = calculate(face_value=1000, coupon_rate=0.0, maturity_years=10, ytm=0.05)
    assert abs(result["duration"] - 10.0) < 0.01


def test_higher_coupon_lower_duration():
    low_coupon = calculate(face_value=1000, coupon_rate=0.02, maturity_years=10, ytm=0.05)
    high_coupon = calculate(face_value=1000, coupon_rate=0.08, maturity_years=10, ytm=0.05)
    assert low_coupon["duration"] > high_coupon["duration"]


# ---------------------------------------------------------------------------
# DV01
# ---------------------------------------------------------------------------

def test_dv01_formula():
    # DV01 = modified_duration * price * 0.0001
    result = calculate(face_value=1000, coupon_rate=0.05, maturity_years=10, ytm=0.05)
    expected_dv01 = result["modified_duration"] * result["price"] * 0.0001
    assert abs(result["dv01"] - expected_dv01) < 1e-6


def test_dv01_positive():
    result = calculate(face_value=1000, coupon_rate=0.05, maturity_years=10, ytm=0.05)
    assert result["dv01"] > 0


# ---------------------------------------------------------------------------
# Convexity
# ---------------------------------------------------------------------------

def test_convexity_positive():
    result = calculate(face_value=1000, coupon_rate=0.05, maturity_years=10, ytm=0.05)
    assert result["convexity"] > 0


def test_longer_maturity_higher_convexity():
    short = calculate(face_value=1000, coupon_rate=0.05, maturity_years=5, ytm=0.05)
    long_ = calculate(face_value=1000, coupon_rate=0.05, maturity_years=20, ytm=0.05)
    assert long_["convexity"] > short["convexity"]


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def test_raises_if_both_ytm_and_price():
    with pytest.raises(ValueError, match="exactly one"):
        calculate(face_value=1000, coupon_rate=0.05, maturity_years=10,
                  ytm=0.05, price=1000.0)


def test_raises_if_neither_ytm_nor_price():
    with pytest.raises(ValueError, match="exactly one"):
        calculate(face_value=1000, coupon_rate=0.05, maturity_years=10)


def test_raises_negative_face_value():
    with pytest.raises(ValueError):
        calculate(face_value=-1000, coupon_rate=0.05, maturity_years=10, ytm=0.05)


def test_raises_negative_maturity():
    with pytest.raises(ValueError):
        calculate(face_value=1000, coupon_rate=0.05, maturity_years=-1, ytm=0.05)


def test_raises_ytm_out_of_range():
    with pytest.raises(ValueError):
        calculate(face_value=1000, coupon_rate=0.05, maturity_years=10, ytm=1.5)
