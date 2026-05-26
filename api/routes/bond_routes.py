"""Bond routes — /api/bond/*"""

from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException

from db.supabase_client import get_client
from skills.bond_calculator import calculate as bond_calc
from api.models.bond_models import (
    BondCalculateRequest, BondCalculateResponse, BondMetrics, BondHistoryItem
)

router = APIRouter(prefix="/bond")


@router.post("/calculate", response_model=BondCalculateResponse)
def calculate_bond(request: BondCalculateRequest):
    db = get_client()

    calc_kwargs = {
        "face_value":     request.face_value,
        "coupon_rate":    request.coupon_rate,
        "maturity_years": request.maturity_years,
    }
    if request.ytm is not None:
        calc_kwargs["ytm"] = request.ytm
    else:
        calc_kwargs["price"] = request.price

    try:
        metrics = bond_calc(**calc_kwargs)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Persist to ciq_bond_calculations
    insert_data = {
        "session_id":        request.session_id,
        "face_value":        request.face_value,
        "coupon_rate":       request.coupon_rate,
        "maturity_years":    request.maturity_years,
        "ytm":               metrics["ytm"],
        "credit_rating":     request.credit_rating,
        "price":             metrics["price"],
        "duration":          metrics["duration"],
        "modified_duration": metrics["modified_duration"],
        "convexity":         metrics["convexity"],
        "dv01":              metrics["dv01"],
    }
    saved = db.table("ciq_bond_calculations").insert(insert_data).execute()
    calc_id = saved.data[0]["id"] if saved.data else None

    return {
        "metrics":        metrics,
        "session_id":     request.session_id,
        "calculation_id": calc_id,
    }


@router.get("/history", response_model=List[BondHistoryItem])
def get_bond_history(session_id: Optional[str] = Query(default=None)):
    db = get_client()
    query = db.table("ciq_bond_calculations").select("*").order("created_at", desc=True)
    if session_id:
        query = query.eq("session_id", session_id)
    result = query.limit(50).execute()
    return result.data or []
