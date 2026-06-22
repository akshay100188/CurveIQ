"""Pure-function unit tests for L1 compute (no DB needed).

Run with pytest, or directly:  python -m tests.test_compute
"""
from pipeline.phase1_compute import THETA, THETA_C, classify_curve


def test_spread_math_hand_computed():
    # 10Y=4.40, 2Y=4.55 -> slope = -0.15
    assert round(4.40 - 4.55, 2) == -0.15


def test_classify_inverted_on_2y():
    # 10Y-2Y well below -THETA -> inverted regardless of 3M
    assert classify_curve(-0.50, 0.20, 0.0) == "inverted"


def test_classify_inverted_via_3m_only():
    # 2019 case: 10Y-2Y grazes flat band (-0.04) but 10Y-3M deeply inverted
    assert classify_curve(-0.04, -0.50, 0.0) == "inverted"


def test_classify_flat_band():
    # both anchors inside the flat band
    assert classify_curve(0.05, 0.08, 0.0) == "flat"
    assert classify_curve(-0.05, 0.30, 0.0) == "flat"


def test_classify_humped():
    # positive slope, strong butterfly above THETA_C -> humped
    assert classify_curve(0.50, 0.60, THETA_C + 0.05) == "humped"


def test_classify_normal():
    # healthy upward slope, no hump
    assert classify_curve(1.20, 1.50, 0.0) == "normal"


def test_threshold_boundaries():
    # exactly at +/-THETA is flat (|slope| <= THETA), just beyond is not
    assert classify_curve(THETA, THETA, 0.0) == "flat"
    assert classify_curve(-THETA - 0.001, 0.5, 0.0) == "inverted"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn(); print(f"  [PASS] {fn.__name__}")
    print(f"\n{len(fns)} unit tests passed")
