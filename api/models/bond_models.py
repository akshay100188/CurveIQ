"""Pydantic models for bond and scenario API endpoints."""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, model_validator


class BondCalculateRequest(BaseModel):
    face_value: float = Field(gt=0, description="Par value in dollars")
    coupon_rate: float = Field(ge=0, le=1, description="Annual coupon rate as decimal (0.05 = 5%)")
    maturity_years: float = Field(gt=0, description="Years to maturity")
    ytm: Optional[float] = Field(default=None, gt=0, lt=1,
                                  description="Annual YTM as decimal — provide ytm OR price")
    price: Optional[float] = Field(default=None, gt=0,
                                    description="Market price in dollars — provide price OR ytm")
    credit_rating: Optional[str] = None
    session_id: Optional[str] = None

    @model_validator(mode="after")
    def check_ytm_or_price(self):
        if self.ytm is None and self.price is None:
            raise ValueError("Provide exactly one of 'ytm' or 'price'")
        if self.ytm is not None and self.price is not None:
            raise ValueError("Provide exactly one of 'ytm' or 'price', not both")
        return self


class BondMetrics(BaseModel):
    price: float
    ytm: float
    duration: float
    modified_duration: float
    convexity: float
    dv01: float


class BondCalculateResponse(BaseModel):
    metrics: BondMetrics
    session_id: Optional[str] = None
    calculation_id: Optional[int] = None


class ScenarioItem(BaseModel):
    shock_bps: int
    price_change_pct: float
    dollar_impact: float
    new_price: float
    new_ytm: float


class ScenarioRunRequest(BaseModel):
    bond_calculation_id: Optional[int] = None
    face_value: Optional[float] = Field(default=None, gt=0)
    coupon_rate: Optional[float] = Field(default=None, ge=0, le=1)
    maturity_years: Optional[float] = Field(default=None, gt=0)
    ytm: Optional[float] = Field(default=None, gt=0, lt=1)
    price: Optional[float] = Field(default=None, gt=0)
    shocks_bps: Optional[List[int]] = Field(default=None)


class ScenarioCustomRequest(BaseModel):
    face_value: float = Field(gt=0)
    coupon_rate: float = Field(ge=0, le=1)
    maturity_years: float = Field(gt=0)
    ytm: Optional[float] = Field(default=None, gt=0, lt=1)
    price: Optional[float] = Field(default=None, gt=0)
    shocks_bps: List[int] = Field(default=[-200, -100, -50, 50, 100, 200])


class ScenarioResponse(BaseModel):
    scenarios: List[ScenarioItem]
    metrics: BondMetrics


class BondHistoryItem(BaseModel):
    id: int
    session_id: Optional[str]
    face_value: float
    coupon_rate: float
    maturity_years: float
    ytm: Optional[float]
    credit_rating: Optional[str]
    price: Optional[float]
    duration: Optional[float]
    modified_duration: Optional[float]
    convexity: Optional[float]
    dv01: Optional[float]
    created_at: datetime
