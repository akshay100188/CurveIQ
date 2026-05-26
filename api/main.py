"""
CurveIQ FastAPI application entry point.

Start: uvicorn api.main:app --reload --port 8000
Docs:  http://localhost:8000/docs
"""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from api.routes.health_routes import router as health_router
from api.routes.curve_routes import router as curve_router
from api.routes.bond_routes import router as bond_router
from api.routes.scenario_routes import router as scenario_router
from api.routes.credit_routes import router as credit_router
from api.routes.agent_routes import router as agent_router

app = FastAPI(
    title="CurveIQ",
    description="US Fixed Income Intelligence Platform — Rate + Credit Risk",
    version="1.0.0",
)

# CORS — allow requests from the frontend URL (set in .env)
frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(curve_router, prefix="/api")
app.include_router(bond_router, prefix="/api")
app.include_router(scenario_router, prefix="/api")
app.include_router(credit_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
