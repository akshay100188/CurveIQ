"""Equity refreshers for the daily job — keep core.curveiq_{sp500,nifty50} current.

S&P 500: re-pull the official FRED `SP500` series (2016→present) and upsert. The
1995–2016 Yahoo backfill already in the table is static and left untouched.
Nifty 50: re-pull a recent window from niftyindices.com (NSE official) and upsert.

Both upserts are idempotent — safe to run daily.
"""
from __future__ import annotations

import http.cookiejar
import json
import urllib.request
from datetime import date, datetime, timedelta, timezone

import requests
from psycopg2.extras import execute_values

from .. import db
from ..config import FRED_API_KEY


def refresh_sp500() -> int:
    """Upsert official FRED SP500 (2016→present) into core.curveiq_sp500."""
    if not FRED_API_KEY:
        raise RuntimeError("FRED_API_KEY not set")
    url = ("https://api.stlouisfed.org/fred/series/observations"
           f"?series_id=SP500&api_key={FRED_API_KEY}&file_type=json"
           "&observation_start=2016-01-01")
    obs = requests.get(url, timeout=30).json()["observations"]
    rows = [(datetime.strptime(o["date"], "%Y-%m-%d").date(), float(o["value"]),
             "FRED SP500 (official)")
            for o in obs if o["value"] not in (".", "", None)]
    with db.cursor() as cur:
        execute_values(cur,
            "insert into core.curveiq_sp500(date,close,source) values %s "
            "on conflict(date) do update set close=excluded.close, source=excluded.source",
            rows, page_size=1000)
    return len(rows)


def refresh_nifty50(lookback_days: int = 800) -> int:
    """Upsert a recent window of official Nifty 50 (niftyindices.com) into
    core.curveiq_nifty50."""
    start = (date.today() - timedelta(days=lookback_days)).strftime("%d-%b-%Y")
    end = date.today().strftime("%d-%b-%Y")
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    hdr = [("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"),
           ("Referer", "https://www.niftyindices.com/reports/historical-data"),
           ("Accept", "application/json, text/javascript, */*; q=0.01"),
           ("Content-Type", "application/json; charset=UTF-8"),
           ("X-Requested-With", "XMLHttpRequest"),
           ("Origin", "https://www.niftyindices.com")]
    op.addheaders = hdr
    op.open("https://www.niftyindices.com/reports/historical-data", timeout=30).read()
    body = json.dumps({"cinfo": json.dumps(
        {"name": "NIFTY 50", "startDate": start, "endDate": end, "indexName": "NIFTY 50"})}).encode()
    req = urllib.request.Request(
        "https://www.niftyindices.com/Backpage.aspx/getHistoricaldatatabletoString",
        data=body, headers=dict(hdr), method="POST")
    raw = json.loads(json.loads(op.open(req, timeout=60).read().decode())["d"])

    def num(x):
        return float(str(x).replace(",", "").strip()) if x not in (None, "", "-") else None
    rows = []
    for r in raw:
        d = datetime.strptime(r["HistoricalDate"].strip(), "%d %b %Y").date()
        rows.append((d, num(r["OPEN"]), num(r["HIGH"]), num(r["LOW"]), num(r["CLOSE"])))
    with db.cursor() as cur:
        execute_values(cur,
            "insert into core.curveiq_nifty50(date,open,high,low,close) values %s "
            "on conflict(date) do update set open=excluded.open,high=excluded.high,"
            "low=excluded.low,close=excluded.close",
            rows, page_size=1000)
    return len(rows)


if __name__ == "__main__":
    print("S&P 500 rows upserted:", refresh_sp500())
    print("Nifty 50 rows upserted:", refresh_nifty50())
