"""Credit stress routes — /api/credit/*"""

import json
import os
from typing import List, Optional
from datetime import date, timedelta

from fastapi import APIRouter, Query, HTTPException

from db.supabase_client import get_client
from skills.stress_scorer import score as stress_score
from api.models.credit_models import (
    CreditStressRow, StressScoreResponse, CrisisPeriod
)

router = APIRouter(prefix="/credit")

# Hardcoded crisis periods for the CrisisReplay page
CRISIS_PERIODS = [
    {
        "name": "2008 Global Financial Crisis",
        "start_date": "2007-01-01",
        "end_date": "2009-06-30",
        "description": "Subprime mortgage crisis, Lehman bankruptcy, systemic banking collapse",
    },
    {
        "name": "2020 COVID-19 Shock",
        "start_date": "2020-01-01",
        "end_date": "2020-07-31",
        "description": "Pandemic-driven market crash, fastest VIX spike in history, rapid Fed response",
    },
    {
        "name": "2011 European Sovereign Debt Crisis",
        "start_date": "2010-06-01",
        "end_date": "2012-12-31",
        "description": "Greek/PIIGS sovereign stress, contagion to US credit markets",
    },
]


def _load_percentiles() -> dict:
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(root, "data", "processed", "stress_percentiles.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


@router.get("/latest", response_model=CreditStressRow)
def get_latest_credit():
    db = get_client()
    result = db.table("ciq_credit_stress_daily").select("*").order(
        "date", desc=True
    ).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="No credit stress data available")
    return result.data[0]


@router.get("/history", response_model=List[CreditStressRow])
def get_credit_history(
    days: int = Query(default=90, ge=1, le=9000),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
):
    db = get_client()
    query = db.table("ciq_credit_stress_daily").select("*")
    if start_date and end_date:
        query = query.gte("date", start_date).lte("date", end_date)
    else:
        since = (date.today() - timedelta(days=days)).isoformat()
        query = query.gte("date", since)
    result = query.order("date", desc=False).execute()
    return result.data or []


@router.get("/stress-score", response_model=StressScoreResponse)
def get_stress_score():
    db = get_client()

    credit = db.table("ciq_credit_stress_daily").select("*").order(
        "date", desc=True
    ).limit(1).execute()
    if not credit.data:
        raise HTTPException(status_code=404, detail="No credit stress data available")

    credit_row = credit.data[0]

    # Get spread_2y10y from yield curve
    yield_row = db.table("ciq_yield_curve_daily").select(
        "spread_2y10y"
    ).order("date", desc=True).limit(1).execute()
    spread_2y10y = (yield_row.data[0]["spread_2y10y"]
                    if yield_row.data else None)

    indicators = {
        "hy_oas":       credit_row.get("hy_oas"),
        "ig_oas":       credit_row.get("ig_oas"),
        "ted_spread":   credit_row.get("ted_spread"),
        "vix":          credit_row.get("vix"),
        "spread_2y10y": spread_2y10y,
    }

    percentiles = _load_percentiles()
    if not percentiles:
        # Fall back to pre-computed values from DB
        return {
            "date":             credit_row["date"],
            "stress_score":     credit_row.get("stress_score"),
            "stress_regime":    credit_row.get("stress_regime"),
            "component_scores": {},
            "components_used":  [],
            "hy_oas":           credit_row.get("hy_oas"),
            "ig_oas":           credit_row.get("ig_oas"),
            "ted_spread":       credit_row.get("ted_spread"),
            "vix":              credit_row.get("vix"),
        }

    scored = stress_score(indicators, percentiles)
    return {
        "date":             credit_row["date"],
        "stress_score":     scored["stress_score"],
        "stress_regime":    scored["stress_regime"],
        "component_scores": scored["component_scores"],
        "components_used":  scored["components_used"],
        "hy_oas":           credit_row.get("hy_oas"),
        "ig_oas":           credit_row.get("ig_oas"),
        "ted_spread":       credit_row.get("ted_spread"),
        "vix":              credit_row.get("vix"),
    }


@router.get("/crisis-periods", response_model=List[CrisisPeriod])
def get_crisis_periods():
    return CRISIS_PERIODS
