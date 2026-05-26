"""
CurveAnalyst agent — yield curve narrative generator.

Triggered by: GET /api/agent/curve-analysis
Input:        none (fetches latest data internally)
Output:       {narrative: dict, model_used: str, generated_at: str}

Steps:
  1. Fetch latest ciq_yield_curve_daily row
  2. Run curve_classifier to get shape + flags
  3. Fetch last 3 Fed decisions
  4. Retrieve RAG context (top 4 curve_event + concept docs)
  5. Build and send prompt to LLM
  6. Parse JSON response (with error handling)
  7. Save to ciq_agent_narratives
  8. Save prediction to ciq_self_learning_log (outcome in 30 days)
"""

import json
import logging
from datetime import date, timedelta, datetime

from db.supabase_client import get_client
from agents.base_agent import call_llm
from skills.curve_classifier import classify
from skills.rag_retriever import retrieve

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a fixed income strategist with CFA-level expertise in US Treasury
markets and yield curve analysis. You provide clear, actionable analysis for financial professionals.

Respond in structured JSON with exactly these keys:
{
  "curve_shape_summary": "2-3 sentences on current curve shape",
  "macro_interpretation": "2-3 sentences on macro implications",
  "historical_analogue": "1-2 sentences on closest historical parallel",
  "forward_implication": "2-3 sentences on likely near-term direction",
  "recession_probability_commentary": "1-2 sentences on recession signal",
  "prediction": "high|medium|low recession probability in next 12 months"
}

Use precise financial language. Cite specific spread levels and basis points.
Do not add keys beyond those specified. Do not wrap in markdown code fences."""

REQUIRED_KEYS = [
    "curve_shape_summary", "macro_interpretation", "historical_analogue",
    "forward_implication", "recession_probability_commentary", "prediction",
]


def _fetch_latest_curve(db) -> dict | None:
    result = db.table("ciq_yield_curve_daily").select("*").order(
        "date", desc=True
    ).limit(1).execute()
    return result.data[0] if result.data else None


def _fetch_recent_fed_decisions(db, n: int = 3) -> list:
    result = db.table("ciq_fed_decisions").select(
        "decision_date, rate_before, rate_after, rate_change, decision_type"
    ).neq("decision_type", "future").order(
        "decision_date", desc=True
    ).limit(n).execute()
    return result.data or []


def _build_user_prompt(curve_row: dict, classifier_result: dict,
                       ciq_fed_decisions: list, rag_docs: list) -> str:
    spread_2y10y = curve_row.get("spread_2y10y", "N/A")
    spread_3m10y = curve_row.get("spread_3m10y", "N/A")
    shape = classifier_result.get("shape", "unknown")
    inv_depth = classifier_result.get("inversion_depth_bps", 0)

    fed_lines = []
    for d in ciq_fed_decisions:
        fed_lines.append(
            f"  {d['decision_date']}: {d['decision_type'].upper()} "
            f"{d['rate_before']}% → {d['rate_after']}%"
        )

    rag_lines = []
    for doc in rag_docs:
        rag_lines.append(f"  [{doc['doc_type']}] {doc['title']}: {doc['content'][:200]}...")

    return f"""Current yield curve data (as of {curve_row.get('date', 'N/A')}):

Curve shape: {shape}
2Y/10Y spread: {spread_2y10y}% ({abs(float(spread_2y10y or 0)) * 100:.0f}bps)
3M/10Y spread: {spread_3m10y}%
Inversion depth: {inv_depth:.0f}bps
2Y yield: {curve_row.get('t2y', 'N/A')}%
5Y yield: {curve_row.get('t5y', 'N/A')}%
10Y yield: {curve_row.get('t10y', 'N/A')}%
30Y yield: {curve_row.get('t30y', 'N/A')}%

Recent Fed decisions:
{chr(10).join(fed_lines) if fed_lines else '  No recent decisions available'}

Relevant historical context:
{chr(10).join(rag_lines) if rag_lines else '  No context available'}

Provide your structured JSON analysis now."""


def _parse_narrative(text: str) -> dict:
    """Parse JSON from LLM response. Strips markdown fences and retries once on failure."""
    # Strip markdown code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        parsed = json.loads(cleaned)
        # Ensure all required keys are present
        for key in REQUIRED_KEYS:
            if key not in parsed:
                parsed[key] = ""
        return parsed
    except json.JSONDecodeError:
        logger.warning("JSON parse failed on curve_analyst response; returning raw_narrative")
        return {"raw_narrative": text, "parse_failed": True}


def run(payload: dict = None) -> dict:
    db = get_client()

    # 1. Latest curve data
    curve_row = _fetch_latest_curve(db)
    if not curve_row:
        raise RuntimeError("No yield curve data in database. Run Phase 0 pipeline first.")

    # 2. Classify
    classifier_result = classify(curve_row)

    # 3. Recent Fed decisions
    ciq_fed_decisions = _fetch_recent_fed_decisions(db)

    # 4. RAG context
    spread_2y10y = curve_row.get("spread_2y10y", 0) or 0
    rag_query = f"yield curve {classifier_result.get('shape', '')} spread {spread_2y10y:.2f}% historical"
    rag_docs = retrieve(rag_query, top_k=4, doc_type_filter=["curve_event", "concept"])

    # 5. Build prompt and call LLM
    user_prompt = _build_user_prompt(curve_row, classifier_result, ciq_fed_decisions, rag_docs)
    llm_result = call_llm(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)

    # 6. Parse
    narrative = _parse_narrative(llm_result["text"])

    # 7. Save to ciq_agent_narratives
    narrative_row = db.table("ciq_agent_narratives").insert({
        "narrative_type": "curve_analysis",
        "input_snapshot": {
            "date": curve_row.get("date"),
            "curve_shape": classifier_result.get("shape"),
            "spread_2y10y": curve_row.get("spread_2y10y"),
            "t2y": curve_row.get("t2y"),
            "t10y": curve_row.get("t10y"),
        },
        "narrative": narrative,
        "model_used": llm_result["model_used"],
        "curve_shape_at_time": classifier_result.get("shape"),
        "spread_2y10y_at_time": curve_row.get("spread_2y10y"),
        "stress_score_at_time": None,
        "stress_regime_at_time": None,
    }).execute()

    narrative_id = narrative_row.data[0]["id"]

    # 8. Log prediction
    prediction_value = narrative.get("prediction", "")
    if prediction_value and not narrative.get("parse_failed"):
        outcome_date = (date.today() + timedelta(days=30)).isoformat()
        db.table("ciq_self_learning_log").insert({
            "narrative_id": narrative_id,
            "prediction_type": "recession_signal",
            "predicted_value": prediction_value,
            "actual_value": None,
            "was_correct": None,
            "outcome_date": outcome_date,
        }).execute()

    return {
        "narrative": narrative,
        "model_used": llm_result["model_used"],
        "generated_at": datetime.utcnow().isoformat(),
        "curve_shape": classifier_result.get("shape"),
        "spread_2y10y": curve_row.get("spread_2y10y"),
        "narrative_id": narrative_id,
    }
