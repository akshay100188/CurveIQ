"""Yield curve routes — /api/curve/*"""

from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException

from db.supabase_client import get_client
from skills.curve_classifier import classify
from api.models.curve_models import (
    YieldCurveRow, CurveShapeResponse, SpreadHistoryItem, FedDecisionItem
)

router = APIRouter(prefix="/curve")


@router.get("/latest", response_model=YieldCurveRow)
def get_latest_curve():
    db = get_client()
    result = db.table("ciq_yield_curve_daily").select("*").order("date", desc=True).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="No yield curve data available")
    return result.data[0]


@router.get("/history", response_model=List[YieldCurveRow])
def get_curve_history(days: int = Query(default=30, ge=1, le=9000)):
    db = get_client()
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=days)).isoformat()
    result = db.table("ciq_yield_curve_daily").select("*").gte(
        "date", since
    ).order("date", desc=False).execute()
    return result.data or []


@router.get("/spreads", response_model=List[SpreadHistoryItem])
def get_spread_history(
    days: int = Query(default=365, ge=1, le=9000),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
):
    db = get_client()
    from datetime import date, timedelta
    query = db.table("ciq_yield_curve_daily").select("date, spread_2y10y, spread_3m10y")
    if start_date and end_date:
        query = query.gte("date", start_date).lte("date", end_date)
    else:
        since = (date.today() - timedelta(days=days)).isoformat()
        query = query.gte("date", since)
    result = query.order("date", desc=False).execute()
    return result.data or []


@router.get("/shape", response_model=CurveShapeResponse)
def get_current_shape():
    db = get_client()
    result = db.table("ciq_yield_curve_daily").select("*").order("date", desc=True).limit(1).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="No yield curve data available")
    row = result.data[0]
    classification = classify(row)
    return {
        "date":                row["date"],
        "shape":               classification["shape"],
        "spread_2y10y":        row.get("spread_2y10y"),
        "spread_3m10y":        row.get("spread_3m10y"),
        "inversion_flag":      classification["inversion_flag"] or False,
        "inversion_depth_bps": classification["inversion_depth_bps"] or 0.0,
        "steepness_score":     classification["steepness_score"],
    }


@router.get("/fed-decisions", response_model=List[FedDecisionItem])
def get_fed_decisions():
    db = get_client()
    result = db.table("ciq_fed_decisions").select("*").neq(
        "decision_type", "future"
    ).order("decision_date", desc=True).execute()
    return result.data or []
