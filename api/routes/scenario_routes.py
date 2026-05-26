"""Scenario routes — /api/scenario/*"""

from fastapi import APIRouter, HTTPException

from db.supabase_client import get_client
from skills.bond_calculator import calculate as bond_calc
from skills.scenario_engine import run as scenario_run
from api.models.bond_models import (
    ScenarioRunRequest, ScenarioCustomRequest, ScenarioResponse, BondMetrics
)

router = APIRouter(prefix="/scenario")


def _resolve_bond_and_run(face_value, coupon_rate, maturity_years, ytm=None,
                          price=None, shocks_bps=None):
    calc_kwargs = {"face_value": face_value, "coupon_rate": coupon_rate,
                   "maturity_years": maturity_years}
    if ytm is not None:
        calc_kwargs["ytm"] = ytm
    else:
        calc_kwargs["price"] = price
    try:
        metrics = bond_calc(**calc_kwargs)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    metrics["face_value"] = face_value
    scenarios = scenario_run(metrics, shocks_bps=shocks_bps)
    return metrics, scenarios


@router.post("/run", response_model=ScenarioResponse)
def run_scenario(request: ScenarioRunRequest):
    db = get_client()

    if request.bond_calculation_id:
        result = db.table("ciq_bond_calculations").select("*").eq(
            "id", request.bond_calculation_id
        ).limit(1).execute()
        if not result.data:
            raise HTTPException(status_code=404,
                                detail=f"bond_calculation_id {request.bond_calculation_id} not found")
        row = result.data[0]
        metrics, scenarios = _resolve_bond_and_run(
            face_value=float(row["face_value"]),
            coupon_rate=float(row["coupon_rate"]),
            maturity_years=float(row["maturity_years"]),
            ytm=float(row["ytm"]),
            shocks_bps=request.shocks_bps,
        )
    else:
        if not all([request.face_value, request.coupon_rate, request.maturity_years]):
            raise HTTPException(status_code=422,
                                detail="Provide bond_calculation_id or full bond params")
        metrics, scenarios = _resolve_bond_and_run(
            face_value=request.face_value,
            coupon_rate=request.coupon_rate,
            maturity_years=request.maturity_years,
            ytm=request.ytm,
            price=request.price,
            shocks_bps=request.shocks_bps,
        )

    return {"scenarios": scenarios, "metrics": metrics}


@router.post("/custom", response_model=ScenarioResponse)
def run_custom_scenario(request: ScenarioCustomRequest):
    metrics, scenarios = _resolve_bond_and_run(
        face_value=request.face_value,
        coupon_rate=request.coupon_rate,
        maturity_years=request.maturity_years,
        ytm=request.ytm,
        price=request.price,
        shocks_bps=request.shocks_bps,
    )
    return {"scenarios": scenarios, "metrics": metrics}
