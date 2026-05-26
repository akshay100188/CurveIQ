"""
Agent orchestrator — routes request_type to the correct agent.

Usage:
    from agents.orchestrator import route

    result = route("curve_analysis", {})
    result = route("bond_advice", {"face_value": 1000, "coupon_rate": 0.05, ...})
    result = route("sysrisk_analysis", {})

Raises:
    ValueError: if request_type is not one of the three registered routes.
"""

from agents import curve_analyst, bond_advisor, sysrisk_analyst

_ROUTES = {
    "curve_analysis":   curve_analyst.run,
    "bond_advice":      bond_advisor.run,
    "sysrisk_analysis": sysrisk_analyst.run,
}


def route(request_type: str, payload: dict) -> dict:
    handler = _ROUTES.get(request_type)
    if not handler:
        valid = ", ".join(_ROUTES.keys())
        raise ValueError(
            f"Unknown request_type '{request_type}'. Valid types: {valid}"
        )
    return handler(payload)
