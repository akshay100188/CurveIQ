"""Agent routes — /api/agent/*"""

from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException

from db.supabase_client import get_client
from agents.orchestrator import route
from api.models.credit_models import (
    AgentNarrativeItem, FeedbackRequest, AccuracyResponse
)

router = APIRouter(prefix="/agent")


@router.get("/curve-analysis")
def get_curve_analysis():
    try:
        return route("curve_analysis", {})
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail={"error": "LLM unavailable", "detail": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "Analysis failed", "detail": str(e)})


@router.post("/bond-advice")
def get_bond_advice(payload: dict):
    try:
        return route("bond_advice", payload)
    except ValueError as e:
        raise HTTPException(status_code=422, detail={"error": "Invalid input", "detail": str(e)})
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail={"error": "LLM unavailable", "detail": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "Analysis failed", "detail": str(e)})


@router.get("/sysrisk-analysis")
def get_sysrisk_analysis():
    try:
        return route("sysrisk_analysis", {})
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail={"error": "LLM unavailable", "detail": str(e)})
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "Analysis failed", "detail": str(e)})


@router.get("/narratives", response_model=List[AgentNarrativeItem])
def get_narratives(
    type: Optional[str] = Query(default=None,
                                 description="Filter by narrative_type: curve_analysis, bond_advice, sysrisk_analysis"),
    limit: int = Query(default=20, ge=1, le=100),
):
    db = get_client()
    query = db.table("ciq_agent_narratives").select("*").order("created_at", desc=True)
    if type:
        query = query.eq("narrative_type", type)
    result = query.limit(limit).execute()
    return result.data or []


@router.post("/feedback")
def submit_feedback(request: FeedbackRequest):
    """
    Store user feedback on a narrative.
    Updates ciq_agent_narratives.user_feedback (not ciq_self_learning_log —
    self-learning evaluation is automated separately).
    """
    db = get_client()
    result = db.table("ciq_agent_narratives").update(
        {"user_feedback": request.is_correct}
    ).eq("id", request.narrative_id).execute()
    if not result.data:
        raise HTTPException(status_code=404,
                            detail={"error": "Narrative not found",
                                    "detail": f"id={request.narrative_id}"})
    return {"status": "ok", "narrative_id": request.narrative_id,
            "user_feedback": request.is_correct}


@router.get("/accuracy", response_model=AccuracyResponse)
def get_accuracy():
    """Aggregated self-learning prediction accuracy."""
    db = get_client()
    all_rows = db.table("ciq_self_learning_log").select(
        "prediction_type, predicted_value, actual_value, was_correct"
    ).execute()
    rows = all_rows.data or []

    total = len(rows)
    evaluated = [r for r in rows if r.get("actual_value") is not None]
    correct = [r for r in evaluated if r.get("was_correct") is True]

    accuracy_pct = (len(correct) / len(evaluated) * 100) if evaluated else None

    by_type: dict = {}
    for r in rows:
        t = r.get("prediction_type", "unknown")
        if t not in by_type:
            by_type[t] = {"total": 0, "evaluated": 0, "correct": 0}
        by_type[t]["total"] += 1
        if r.get("actual_value") is not None:
            by_type[t]["evaluated"] += 1
            if r.get("was_correct"):
                by_type[t]["correct"] += 1

    for t in by_type:
        ev = by_type[t]["evaluated"]
        by_type[t]["accuracy_pct"] = (
            round(by_type[t]["correct"] / ev * 100, 1) if ev > 0 else None
        )

    return {
        "total_predictions": total,
        "outcomes_evaluated": len(evaluated),
        "accuracy_pct": round(accuracy_pct, 1) if accuracy_pct is not None else None,
        "by_type": by_type,
    }
