"""Tests for skills/scenario_engine.py"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from skills.scenario_engine import run
from skills.bond_calculator import calculate


def make_metrics(coupon=0.05, maturity=10, ytm=0.05, face=1000):
    m = calculate(face_value=face, coupon_rate=coupon, maturity_years=maturity, ytm=ytm)
    m["face_value"] = face
    return m


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

def test_default_six_scenarios():
    metrics = make_metrics()
    results = run(metrics)
    assert len(results) == 6


def test_output_keys():
    metrics = make_metrics()
    result = run(metrics)[0]
    assert set(result.keys()) == {
        "shock_bps", "price_change_pct", "dollar_impact", "new_price", "new_ytm"
    }


def test_ordered_by_shock_ascending():
    metrics = make_metrics()
    results = run(metrics)
    shocks = [r["shock_bps"] for r in results]
    assert shocks == sorted(shocks)


def test_custom_shocks():
    metrics = make_metrics()
    results = run(metrics, shocks_bps=[-50, 0, 50])
    shocks = [r["shock_bps"] for r in results]
    assert shocks == [-50, 0, 50]


# ---------------------------------------------------------------------------
# Direction correctness
# ---------------------------------------------------------------------------

def test_rate_rise_negative_price_change():
    # Rates up → price down for a standard bond
    metrics = make_metrics()
    results = {r["shock_bps"]: r for r in run(metrics)}
    assert results[100]["price_change_pct"] < 0
    assert results[200]["price_change_pct"] < 0


def test_rate_fall_positive_price_change():
    # Rates down → price up
    metrics = make_metrics()
    results = {r["shock_bps"]: r for r in run(metrics)}
    assert results[-100]["price_change_pct"] > 0
    assert results[-200]["price_change_pct"] > 0


def test_zero_shock_zero_change():
    metrics = make_metrics()
    results = run(metrics, shocks_bps=[0])
    assert abs(results[0]["price_change_pct"]) < 1e-6
    assert abs(results[0]["dollar_impact"]) < 0.01
    assert abs(results[0]["new_price"] - metrics["price"]) < 0.01


# ---------------------------------------------------------------------------
# Convexity asymmetry
# ---------------------------------------------------------------------------

def test_convexity_asymmetry():
    # Due to positive convexity: gain from rate fall > loss from equal rate rise
    metrics = make_metrics()
    results = {r["shock_bps"]: r for r in run(metrics)}
    gain_100 = results[-100]["price_change_pct"]
    loss_100 = results[100]["price_change_pct"]
    assert gain_100 > abs(loss_100), "Positive convexity: gain > loss for same shock size"


def test_larger_shock_larger_impact():
    metrics = make_metrics()
    results = {r["shock_bps"]: r for r in run(metrics)}
    assert abs(results[200]["price_change_pct"]) > abs(results[100]["price_change_pct"])


# ---------------------------------------------------------------------------
# Dollar impact and new price consistency
# ---------------------------------------------------------------------------

def test_dollar_impact_formula():
    metrics = make_metrics(face=1000)
    results = run(metrics, shocks_bps=[100])
    r = results[0]
    expected_dollar = 1000 * r["price_change_pct"] / 100
    assert abs(r["dollar_impact"] - expected_dollar) < 0.01


def test_new_price_formula():
    metrics = make_metrics()
    results = run(metrics, shocks_bps=[100])
    r = results[0]
    expected_new_price = metrics["price"] * (1 + r["price_change_pct"] / 100)
    assert abs(r["new_price"] - expected_new_price) < 0.01


def test_new_ytm_formula():
    metrics = make_metrics(ytm=0.05)
    results = run(metrics, shocks_bps=[100])
    r = results[0]
    assert abs(r["new_ytm"] - 0.06) < 1e-6  # 0.05 + 100bps = 0.06


# ---------------------------------------------------------------------------
# Higher duration bond has larger price impact
# ---------------------------------------------------------------------------

def test_longer_duration_larger_impact():
    short = make_metrics(maturity=2, ytm=0.05)
    long_ = make_metrics(maturity=20, ytm=0.05)
    short_results = {r["shock_bps"]: r for r in run(short)}
    long_results = {r["shock_bps"]: r for r in run(long_)}
    assert abs(long_results[100]["price_change_pct"]) > abs(short_results[100]["price_change_pct"])
