"""FRED (Federal Reserve Economic Data) client.

FRED is the authentic source for the US toolkit: US Treasury CMT yields, official
FRED-computed spreads, TIPS-derived real yields / breakevens, the fed funds rate,
and the NBER recession indicator. All series are US-gov / OECD public data.
"""
from __future__ import annotations

import time
from datetime import date, datetime

import requests

from ..config import FRED_API_KEY

BASE = "https://api.stlouisfed.org/fred"


def _get(path: str, params: dict) -> dict:
    if not FRED_API_KEY:
        raise RuntimeError("FRED_API_KEY not set in .env")
    params = {**params, "api_key": FRED_API_KEY, "file_type": "json"}
    last_err = None
    for attempt in range(1, 4):
        try:
            r = requests.get(f"{BASE}/{path}", params=params, timeout=30)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            last_err = e
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"FRED request failed for {path}: {last_err}")


def series_meta(fred_id: str) -> dict:
    """Return the series metadata (title, observation range, frequency, units)."""
    return _get("series", {"series_id": fred_id})["seriess"][0]


def observations(fred_id: str, start: str = "1900-01-01") -> list[tuple[date, float]]:
    """Return [(obs_date, value), ...] with missing values ('.') dropped."""
    data = _get("series/observations",
                {"series_id": fred_id, "observation_start": start})
    out: list[tuple[date, float]] = []
    for o in data["observations"]:
        v = o["value"]
        if v not in (".", "", None):
            out.append((datetime.strptime(o["date"], "%Y-%m-%d").date(), float(v)))
    return out
