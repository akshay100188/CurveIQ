"""Pydantic models for credit stress API endpoints."""

from typing import Optional, Dict
from datetime import date
from pydantic import BaseModel


class CreditStressRow(BaseModel):
    date: date
    hy_oas: Optional[float] = None
    ig_oas: Optional[float] = None
    ted_spread: Optional[float] = None
    vix: Optional[float] = None
    sofr: Optional[float] = None
    obfr: Optional[float] = None
    stress_score: Optional[float] = None
    stress_regime: Optional[str] = None


class StressScoreResponse(BaseModel):
    date: date
    stress_score: Optional[float] = None
    stress_regime: Optional[str] = None
    component_scores: Dict[str, float] = {}
    components_used: list = []
    hy_oas: Optional[float] = None
    ig_oas: Optional[float] = None
    ted_spread: Optional[float] = None
    vix: Optional[float] = None


class CrisisPeriod(BaseModel):
    name: str
    start_date: date
    end_date: date
    description: str


class AgentNarrativeItem(BaseModel):
    id: int
    narrative_type: str
    narrative: dict
    model_used: Optional[str] = None
    curve_shape_at_time: Optional[str] = None
    spread_2y10y_at_time: Optional[float] = None
    stress_score_at_time: Optional[float] = None
    stress_regime_at_time: Optional[str] = None
    user_feedback: Optional[bool] = None
    created_at: str


class FeedbackRequest(BaseModel):
    narrative_id: int
    is_correct: bool


class AccuracyResponse(BaseModel):
    total_predictions: int
    outcomes_evaluated: int
    accuracy_pct: Optional[float] = None
    by_type: Dict[str, dict] = {}
