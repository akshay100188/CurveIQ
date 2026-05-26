"""GET /api/health — system status check."""

from fastapi import APIRouter
from db.supabase_client import get_client
import os

router = APIRouter()


@router.get("/health")
def health_check():
    db = get_client()
    result = {"status": "ok", "last_yield_date": None, "last_credit_date": None,
              "last_curve_analysis": None, "last_sysrisk_analysis": None,
              "anthropic_available": bool(os.environ.get("ANTHROPIC_API_KEY")),
              "openai_available": bool(os.environ.get("OPENAI_API_KEY")),
              "supabase_connected": False}
    try:
        yc = db.table("ciq_yield_curve_daily").select("date").order("date", desc=True).limit(1).execute()
        if yc.data:
            result["last_yield_date"] = yc.data[0]["date"]

        cs = db.table("ciq_credit_stress_daily").select("date").order("date", desc=True).limit(1).execute()
        if cs.data:
            result["last_credit_date"] = cs.data[0]["date"]

        ca = db.table("ciq_agent_narratives").select("created_at").eq(
            "narrative_type", "curve_analysis"
        ).order("created_at", desc=True).limit(1).execute()
        if ca.data:
            result["last_curve_analysis"] = ca.data[0]["created_at"]

        sr = db.table("ciq_agent_narratives").select("created_at").eq(
            "narrative_type", "sysrisk_analysis"
        ).order("created_at", desc=True).limit(1).execute()
        if sr.data:
            result["last_sysrisk_analysis"] = sr.data[0]["created_at"]

        result["supabase_connected"] = True
    except Exception as e:
        result["status"] = "degraded"
        result["error"] = str(e)

    return result
