"""Central configuration: env loading + the authoritative series catalog.

Every series CurveIQ ingests is declared here with its authentic source, role
(market vs administered), and tenor. This module is the single source of truth
for *what* data is allowed into the system and *where it comes from* — the data
authenticity contract lives here.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _load_env() -> dict[str, str]:
    vals: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip()
    # real environment overrides file
    for k in ("DATABASE_URL", "SUPABASE_URL", "SUPABASE_SERVICE_KEY",
              "SUPABASE_KEY", "FRED_API_KEY"):
        if os.environ.get(k):
            vals[k] = os.environ[k]
    return vals


ENV = _load_env()
FRED_API_KEY = ENV.get("FRED_API_KEY", "")
DATABASE_URL = ENV.get("DATABASE_URL", "")

# Schema CurveIQ writes to (reads come from `bond` + `core`).
WRITE_SCHEMA = "curveiq"

# ---------------------------------------------------------------------------
# Series catalog
# ---------------------------------------------------------------------------
# role:  'market'       -> a freely-traded price/yield; may sit on a market axis
#        'administered' -> a policy/set rate; MUST NEVER be plotted as market move
# tenor_months: set for curve points; None for spreads/policy/equity.
ROLE_MARKET = "market"
ROLE_ADMIN = "administered"


@dataclass(frozen=True)
class Series:
    series_id: str          # canonical id used inside curveiq
    country: str            # 'US' | 'IN'
    role: str               # ROLE_MARKET | ROLE_ADMIN
    category: str           # 'curve' | 'spread' | 'real' | 'breakeven' | 'policy' | 'equity'
    source: str             # human-readable authentic source
    unit: str               # 'percent' | 'index'
    fred_id: str | None = None      # FRED series id, if pulled from FRED
    tenor_months: int | None = None # set only for curve tenor points


# --- US full toolkit (FRED — Federal Reserve / US Treasury, authentic) -------
US_CURVE: list[Series] = [
    Series("US_DGS1MO", "US", ROLE_MARKET, "curve", "FRED DGS1MO (US Treasury CMT)", "percent", "DGS1MO", 1),
    Series("US_DGS3MO", "US", ROLE_MARKET, "curve", "FRED DGS3MO (US Treasury CMT)", "percent", "DGS3MO", 3),
    Series("US_DGS6MO", "US", ROLE_MARKET, "curve", "FRED DGS6MO (US Treasury CMT)", "percent", "DGS6MO", 6),
    Series("US_DGS1",   "US", ROLE_MARKET, "curve", "FRED DGS1 (US Treasury CMT)",   "percent", "DGS1",   12),
    Series("US_DGS2",   "US", ROLE_MARKET, "curve", "FRED DGS2 (US Treasury CMT)",   "percent", "DGS2",   24),
    Series("US_DGS3",   "US", ROLE_MARKET, "curve", "FRED DGS3 (US Treasury CMT)",   "percent", "DGS3",   36),
    Series("US_DGS5",   "US", ROLE_MARKET, "curve", "FRED DGS5 (US Treasury CMT)",   "percent", "DGS5",   60),
    Series("US_DGS7",   "US", ROLE_MARKET, "curve", "FRED DGS7 (US Treasury CMT)",   "percent", "DGS7",   84),
    Series("US_DGS10",  "US", ROLE_MARKET, "curve", "FRED DGS10 (US Treasury CMT)",  "percent", "DGS10",  120),
    Series("US_DGS20",  "US", ROLE_MARKET, "curve", "FRED DGS20 (US Treasury CMT)",  "percent", "DGS20",  240),
    Series("US_DGS30",  "US", ROLE_MARKET, "curve", "FRED DGS30 (US Treasury CMT)",  "percent", "DGS30",  360),
]

US_SPREADS: list[Series] = [
    Series("US_T10Y2Y", "US", ROLE_MARKET, "spread", "FRED T10Y2Y (10Y-2Y)", "percent", "T10Y2Y"),
    Series("US_T10Y3M", "US", ROLE_MARKET, "spread", "FRED T10Y3M (10Y-3M)", "percent", "T10Y3M"),
]

US_REAL_BREAKEVEN: list[Series] = [
    Series("US_DFII5",  "US", ROLE_MARKET, "real",      "FRED DFII5 (5Y TIPS real yield)",  "percent", "DFII5"),
    Series("US_DFII10", "US", ROLE_MARKET, "real",      "FRED DFII10 (10Y TIPS real yield)", "percent", "DFII10"),
    Series("US_T5YIE",  "US", ROLE_MARKET, "breakeven", "FRED T5YIE (5Y breakeven inflation)",  "percent", "T5YIE"),
    Series("US_T10YIE", "US", ROLE_MARKET, "breakeven", "FRED T10YIE (10Y breakeven inflation)", "percent", "T10YIE"),
]

US_POLICY: list[Series] = [
    Series("US_FEDFUNDS", "US", ROLE_ADMIN, "policy", "FRED FEDFUNDS (effective fed funds)", "percent", "FEDFUNDS"),
    Series("US_DFEDTARU", "US", ROLE_ADMIN, "policy", "FRED DFEDTARU (target range upper)",  "percent", "DFEDTARU"),
    Series("US_DFEDTARL", "US", ROLE_ADMIN, "policy", "FRED DFEDTARL (target range lower)",  "percent", "DFEDTARL"),
]

# --- India constrained companion (FRED/OECD — authentic, fresher than the bond
# copy). Monthly. India has NO free full curve, so these are standalone levels:
# they populate rates_timeseries only, never curve_points (see ingest guard).
IN_RATES: list[Series] = [
    Series("IN_10Y_GSEC",    "IN", ROLE_MARKET, "curve",  "FRED INDIRLTLT01STM (OECD, India 10Y G-Sec)", "percent", "INDIRLTLT01STM", 120),
    Series("IN_3M_INTERBANK","IN", ROLE_MARKET, "curve",  "FRED INDIR3TIB01STM (OECD, India 3M interbank)", "percent", "INDIR3TIB01STM", 3),
    Series("IN_CALL_MONEY",  "IN", ROLE_ADMIN,  "policy", "FRED IRSTCI01INM156N (OECD IRSTCI call money/policy composite)", "percent", "IRSTCI01INM156N"),
]

# All FRED-sourced series to ingest in Phase 0.
FRED_SERIES: list[Series] = US_CURVE + US_SPREADS + US_REAL_BREAKEVEN + US_POLICY + IN_RATES

# FRED recession flag — drives the regimes table, not rates_timeseries.
USREC_FRED_ID = "USREC"   # NBER-based recession indicator, monthly 0/1

# ---------------------------------------------------------------------------
# Existing authentic series already in the `bond` schema (NOT yfinance).
# The `bond.series_catalog.country` column is KNOWN-WRONG (all 'IN'); we override
# country here so the canonical store is correct.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BondImport:
    src_series_id: str      # series_id in bond.observations_*
    dst_series_id: str      # canonical id in curveiq.rates_timeseries
    country: str
    role: str
    category: str
    obs_table: str          # bond.observations_{daily,monthly,...}
    date_col: str           # date column in that table
    source: str
    tenor_months: int | None = None


BOND_IMPORTS: list[BondImport] = [
    # India RBI repo (administered, daily). Sourced locally from RBI; the bond
    # copy is fresh (to ~2026-05) and has no clean FRED daily equivalent, so it
    # stays a bond import. India 10Y / call money / 3M now come live from FRED
    # (see IN_RATES) — fresher and spec-designated.
    BondImport("IN_REPO_RATE", "IN_REPO_RATE", "IN", ROLE_ADMIN, "policy",
               "bond.observations_daily", "date",
               "RBI (India policy repo rate)"),
]

# ---------------------------------------------------------------------------
# Equity (already loaded into core.curveiq_* from official/approved sources).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EquityImport:
    dst_series_id: str
    country: str
    src_table: str          # core.curveiq_*
    source: str


EQUITY_IMPORTS: list[EquityImport] = [
    EquityImport("US_SP500",  "US", "core.curveiq_sp500",
                 "FRED SP500 (official, 2016+) + Yahoo ^GSPC (1995-2016)"),
    EquityImport("IN_NIFTY50", "IN", "core.curveiq_nifty50",
                 "niftyindices.com (NSE official)"),
]

# ---------------------------------------------------------------------------
# India crisis windows (no NBER analog) — spec §4 constants.
# ---------------------------------------------------------------------------
INDIA_CRISIS_WINDOWS = [
    ("taper_tantrum", "2013-05-01", "2013-09-30", "manual"),
    ("covid",         "2020-02-01", "2020-04-30", "manual"),
]

# ---------------------------------------------------------------------------
# US named crisis bands for the rates & spread timeline (spec §4/§8). These are
# the four shaded episodes on the 10Y/2Y/spread chart — distinct from the 24
# generic NBER `nber_recession` windows. 2008 & COVID align with NBER recessions;
# Taper Tantrum is a rates episode (no recession); the 2026 US–West Asia war is
# manual and OPEN-ENDED (end_date NULL → ongoing). The war is the yields-UP
# counter-case to the flight-to-safety (yields-down) episodes.
# (regime_name, start_date, end_date|None, source)
# ---------------------------------------------------------------------------
US_CRISIS_WINDOWS = [
    ("gfc_2008",          "2007-12-01", "2009-06-30", "NBER"),
    ("taper_tantrum",     "2013-05-01", "2013-09-30", "manual"),
    ("covid",             "2020-02-01", "2020-04-30", "NBER"),
    ("westasia_war_2026", "2026-02-28", None,         "manual"),
]
