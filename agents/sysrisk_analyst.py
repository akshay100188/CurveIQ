"""
SysRiskAnalyst agent — credit and systemic risk narrative generator.

Triggered by: GET /api/agent/sysrisk-analysis
Input:        none (fetches latest data internally)
Output:       {stress_score, regime, narrative, model_used, generated_at}

Steps:
  1. Fetch latest ciq_credit_stress_daily row
  2. Fetch latest ciq_yield_curve_daily for spread_2y10y context
  3. Build indicators dict and load stress percentiles
  4. Retrieve RAG context (top 5 curve_event + concept + self_learning)
  5. Build and send prompt to LLM
  6. Parse JSON response
  7. Save to ciq_agent_narratives
  8. Save prediction to ciq_self_learning_log (outcome in 30 days)
"""

import json
import logging
from datetime import date, timedelta, datetime

from db.supabase_client import get_client
from agents.base_agent import call_llm
from skills.rag_retriever import retrieve

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a credit market strategist specialising in systemic risk and
financial stability. You analyse credit spreads, interbank stress indicators, and market
contagion signals.

Respond in structured JSON with exactly these keys:
{
  "stress_summary": "2-3 sentences on current stress environment",
  "indicator_breakdown": "2-3 sentences on which indicators are elevated",
  "historical_analogue": "1-2 sentences on closest crisis comparison",
  "contagion_risk": "1-2 sentences on spillover risk assessment",
  "early_warning_assessment": "1-2 sentences on forward-looking signal",
  "prediction": "rising|stable|falling stress in next 30 days"
}

Reference specific OAS levels, VIX values, and spread numbers.
Do not add keys beyond those specified. Do not wrap in markdown code fences."""

REQUIRED_KEYS = [
    "stress_summary", "indicator_breakdown", "historical_analogue",
    "contagion_risk", "early_warning_assessment", "prediction",
]


def _fetch_latest_credit(db) -> dict | None:
    result = db.table("ciq_credit_stress_daily").select("*").order(
        "date", desc=True
    ).limit(1).execute()
    return result.data[0] if result.data else None


def _fetch_latest_yield(db) -> dict | None:
    result = db.table("ciq_yield_curve_daily").select(
        "date, spread_2y10y, curve_shape, t2y, t10y"
    ).order("date", desc=True).limit(1).execute()
    return result.data[0] if result.data else None


def _build_user_prompt(credit_row: dict, yield_row: dict,
                       rag_docs: list) -> str:
    spread = (yield_row or {}).get("spread_2y10y", "N/A")
    curve_shape = (yield_row or {}).get("curve_shape", "unknown")

    rag_lines = [f"  [{doc['doc_type']}] {doc['title']}: {doc['content'][:200]}..."
                 for doc in rag_docs]

    return f"""Current systemic risk indicators (as of {credit_row.get('date', 'N/A')}):

Credit spreads:
  HY OAS (High Yield): {credit_row.get('hy_oas', 'N/A')}bps
  IG OAS (Investment Grade): {credit_row.get('ig_oas', 'N/A')}bps

Interbank stress:
  TED Spread: {credit_row.get('ted_spread', 'N/A')}%
  SOFR: {credit_row.get('sofr', 'N/A')}%
  OBFR: {credit_row.get('obfr', 'N/A')}%

Market volatility:
  VIX: {credit_row.get('vix', 'N/A')}

Composite stress score: {credit_row.get('stress_score', 'N/A')} / 100
Stress regime: {credit_row.get('stress_regime', 'N/A').upper() if credit_row.get('stress_regime') else 'N/A'}

Yield curve context:
  2Y/10Y spread: {spread}%  ({curve_shape})

Historical context and self-learning:
{chr(10).join(rag_lines) if rag_lines else '  No context available'}

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
        logger.warning("JSON parse failed on sysrisk_analyst response")
        return {"raw_narrative": text, "parse_failed": True}


def run(payload: dict = None) -> dict:
    db = get_client()

    # 1 & 2. Fetch latest data
    credit_row = _fetch_latest_credit(db)
    if not credit_row:
        raise RuntimeError("No credit stress data in database. Run Phase 0 pipeline first.")

    yield_row = _fetch_latest_yield(db)

    # 3. RAG context
    regime = credit_row.get("stress_regime", "calm")
    hy_oas = credit_row.get("hy_oas", 0) or 0
    rag_query = f"systemic risk credit stress {regime} {hy_oas:.0f}bps historical"
    rag_docs = retrieve(
        rag_query, top_k=5,
        doc_type_filter=["curve_event", "concept", "self_learning"]
    )

    # 4. Build prompt and call LLM
    user_prompt = _build_user_prompt(credit_row, yield_row or {}, rag_docs)
    llm_result = call_llm(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)

    # 5. Parse
    narrative = _parse_narrative(llm_result["text"])

    # 6. Save to ciq_agent_narratives
    narrative_row = db.table("ciq_agent_narratives").insert({
        "narrative_type": "sysrisk_analysis",
        "input_snapshot": {
            "date":          credit_row.get("date"),
            "hy_oas":        credit_row.get("hy_oas"),
            "vix":           credit_row.get("vix"),
            "ted_spread":    credit_row.get("ted_spread"),
            "stress_score":  credit_row.get("stress_score"),
            "stress_regime": credit_row.get("stress_regime"),
        },
        "narrative": narrative,
        "model_used": llm_result["model_used"],
        "curve_shape_at_time": (yield_row or {}).get("curve_shape"),
        "spread_2y10y_at_time": (yield_row or {}).get("spread_2y10y"),
        "stress_score_at_time": credit_row.get("stress_score"),
        "stress_regime_at_time": credit_row.get("stress_regime"),
    }).execute()

    narrative_id = narrative_row.data[0]["id"]

    # 7. Log prediction
    prediction_value = narrative.get("prediction", "")
    if prediction_value and not narrative.get("parse_failed"):
        outcome_date = (date.today() + timedelta(days=30)).isoformat()
        db.table("ciq_self_learning_log").insert({
            "narrative_id": narrative_id,
            "prediction_type": "stress_direction",
            "predicted_value": prediction_value,
            "actual_value": None,
            "was_correct": None,
            "outcome_date": outcome_date,
        }).execute()

    return {
        "stress_score":   credit_row.get("stress_score"),
        "regime":         credit_row.get("stress_regime"),
        "narrative":      narrative,
        "model_used":     llm_result["model_used"],
        "generated_at":   datetime.utcnow().isoformat(),
        "narrative_id":   narrative_id,
    }
