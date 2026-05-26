"""Pydantic models for yield curve API endpoints."""

from typing import Optional
from datetime import date
from pydantic import BaseModel


class YieldCurveRow(BaseModel):
    date: date
    t1m: Optional[float] = None
    t3m: Optional[float] = None
    t6m: Optional[float] = None
    t1y: Optional[float] = None
    t2y: Optional[float] = None
    t3y: Optional[float] = None
    t5y: Optional[float] = None
    t7y: Optional[float] = None
    t10y: Optional[float] = None
    t20y: Optional[float] = None
    t30y: Optional[float] = None
    spread_2y10y: Optional[float] = None
    spread_3m10y: Optional[float] = None
    curve_shape: Optional[str] = None


class CurveShapeResponse(BaseModel):
    date: date
    shape: Optional[str] = None
    spread_2y10y: Optional[float] = None
    spread_3m10y: Optional[float] = None
    inversion_flag: bool = False
    inversion_depth_bps: float = 0.0
    steepness_score: Optional[float] = None


class SpreadHistoryItem(BaseModel):
    date: date
    spread_2y10y: Optional[float] = None
    spread_3m10y: Optional[float] = None


class FedDecisionItem(BaseModel):
    decision_date: date
    rate_before: Optional[float] = None
    rate_after: Optional[float] = None
    rate_change: Optional[float] = None
    decision_type: str
    statement_summary: Optional[str] = None
