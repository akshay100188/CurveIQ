"""
BondAdvisor agent — bond risk commentary generator.

Triggered by: POST /api/agent/bond-advice
Input (one of two modes):
  MODE A — inline params:
    {face_value, coupon_rate, maturity_years, ytm|price, credit_rating?}
  MODE B — database lookup:
    {bond_calculation_id: int}
Output: {metrics: dict, scenarios: list, narrative: dict, model_used: str}

Steps:
  1. Resolve bond params (from payload or from ciq_bond_calculations table)
  2. Run bond_calculator
  3. Run scenario_engine (default 6 shocks)
  4. Fetch current curve shape
  5. Retrieve RAG context (top 3 concept docs)
  6. Build and send prompt to LLM
  7. Parse JSON response
  8. Save to ciq_agent_narratives
"""

import json
import logging
from datetime import datetime

from db.supabase_client import get_client
from agents.base_agent import call_llm
from skills.bond_calculator import calculate as bond_calc
from skills.scenario_engine import run as scenario_run
from skills.rag_retriever import retrieve

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a fixed income portfolio analyst with expertise in bond risk metrics.
You explain complex risk measures clearly to investment professionals.

Respond in structured JSON with exactly these keys:
{
  "risk_summary": "2-3 sentences overall risk assessment",
  "duration_interpretation": "1-2 sentences on duration in current rate environment",
  "scenario_narrative": "2-3 sentences on most important shock scenarios",
  "recommendation": "1-2 sentences actionable guidance"
}

Reference specific numbers from the metrics provided.
Do not add keys beyond those specified. Do not wrap in markdown code fences."""

REQUIRED_KEYS = ["risk_summary", "duration_interpretation", "scenario_narrative", "recommendation"]


def _resolve_bond_params(payload: dict, db) -> dict:
    """
    Return bond input parameters from either inline payload or DB lookup.
    Raises ValueError if neither is valid.
    """
    bond_calc_id = payload.get("bond_calculation_id")

    if bond_calc_id:
        result = db.table("ciq_bond_calculations").select("*").eq(
            "id", bond_calc_id
        ).limit(1).execute()
        if not result.data:
            raise ValueError(f"bond_calculation_id {bond_calc_id} not found")
        row = result.data[0]
        params = {
            "face_value":     float(row["face_value"]),
            "coupon_rate":    float(row["coupon_rate"]),
            "maturity_years": float(row["maturity_years"]),
            "ytm":            float(row["ytm"]),
            "credit_rating":  row.get("credit_rating"),
        }
    else:
        required = ["face_value", "coupon_rate", "maturity_years"]
        for field in required:
            if field not in payload:
                raise ValueError(f"Missing required field: {field}")
        params = {
            "face_value":     float(payload["face_value"]),
            "coupon_rate":    float(payload["coupon_rate"]),
            "maturity_years": float(payload["maturity_years"]),
            "credit_rating":  payload.get("credit_rating"),
        }
        # Exactly one of ytm or price must be provided
        if "ytm" in payload and payload["ytm"] is not None:
            params["ytm"] = float(payload["ytm"])
        elif "price" in payload and payload["price"] is not None:
            params["price"] = float(payload["price"])
        else:
            raise ValueError("Provide either 'ytm' or 'price' in bond params")

    return params


def _fetch_current_curve_shape(db) -> str:
    result = db.table("ciq_yield_curve_daily").select(
        "curve_shape, spread_2y10y, t10y"
    ).order("date", desc=True).limit(1).execute()
    if result.data:
        row = result.data[0]
        return f"{row.get('curve_shape', 'unknown')} (2Y/10Y: {row.get('spread_2y10y', 'N/A')}%)"
    return "unknown"


def _build_user_prompt(params: dict, metrics: dict, scenarios: list,
                       curve_context: str, rag_docs: list) -> str:
    scenario_lines = []
    for s in scenarios:
        direction = "▲" if s["shock_bps"] > 0 else ("▼" if s["shock_bps"] < 0 else "–")
        scenario_lines.append(
            f"  {direction}{abs(s['shock_bps'])}bps: {s['price_change_pct']:+.2f}%  "
            f"(${s['dollar_impact']:+,.0f})  new_price=${s['new_price']:.2f}"
        )

    rag_lines = [f"  {doc['title']}: {doc['content'][:180]}..." for doc in rag_docs]

    return f"""Bond analysis request:

Bond parameters:
  Face value: ${params['face_value']:,.0f}
  Coupon rate: {params['coupon_rate']*100:.2f}%
  Maturity: {params['maturity_years']:.1f} years
  Credit rating: {params.get('credit_rating', 'Not specified')}

Calculated metrics:
  Price: ${metrics['price']:,.2f}
  YTM: {metrics['ytm']*100:.3f}%
  Macaulay Duration: {metrics['duration']:.2f} years
  Modified Duration: {metrics['modified_duration']:.4f}
  Convexity: {metrics['convexity']:.4f}
  DV01: ${metrics['dv01']:,.2f}

Rate shock scenarios (price change %  |  dollar impact):
{chr(10).join(scenario_lines)}

Current yield curve: {curve_context}

Fixed income concepts (for context):
{chr(10).join(rag_lines) if rag_lines else '  None available'}

Provide your structured JSON analysis now."""


def _parse_narrative(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        parsed = json.loads(cleaned)
        for key in REQUIRED_KEYS:
            if key not in parsed:
                parsed[key] = ""
        return parsed
    except json.JSONDecodeError:
        logger.warning("JSON parse failed on bond_advisor response")
        return {"raw_narrative": text, "parse_failed": True}


def run(payload: dict) -> dict:
    db = get_client()

    # 1. Resolve bond params
    params = _resolve_bond_params(payload, db)

    # 2. Calculate bond metrics
    calc_kwargs = {k: v for k, v in params.items()
                  if k in ("face_value", "coupon_rate", "maturity_years", "ytm", "price")
                  and v is not None}
    metrics = bond_calc(**calc_kwargs)
    metrics["face_value"] = params["face_value"]  # attach for scenario engine

    # 3. Scenario engine
    scenarios = scenario_run(metrics)

    # 4. Current curve context
    curve_context = _fetch_current_curve_shape(db)

    # 5. RAG context
    rag_query = f"bond duration {metrics['duration']:.1f} rate shock risk"
    rag_docs = retrieve(rag_query, top_k=3, doc_type_filter=["concept"])

    # 6. LLM call
    user_prompt = _build_user_prompt(params, metrics, scenarios, curve_context, rag_docs)
    llm_result = call_llm(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)

    # 7. Parse
    narrative = _parse_narrative(llm_result["text"])

    # 8. Save to ciq_agent_narratives
    db.table("ciq_agent_narratives").insert({
        "narrative_type": "bond_advice",
        "input_snapshot": {
            "face_value":     params["face_value"],
            "coupon_rate":    params["coupon_rate"],
            "maturity_years": params["maturity_years"],
            "ytm":            metrics["ytm"],
            "credit_rating":  params.get("credit_rating"),
        },
        "narrative": narrative,
        "model_used": llm_result["model_used"],
        "curve_shape_at_time": None,
        "spread_2y10y_at_time": None,
        "stress_score_at_time": None,
        "stress_regime_at_time": None,
    }).execute()

    return {
        "metrics":    {k: v for k, v in metrics.items() if k != "face_value"},
        "scenarios":  scenarios,
        "narrative":  narrative,
        "model_used": llm_result["model_used"],
        "generated_at": datetime.utcnow().isoformat(),
    }
