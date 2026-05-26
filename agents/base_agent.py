"""
Base LLM caller with Claude primary and GPT-4o-mini fallback.

Usage:
    from agents.base_agent import call_llm

    result = call_llm(system_prompt="...", user_prompt="...")
    # result = {"text": "...", "model_used": "claude-sonnet-4-6"}

Behaviour:
  1. Try Anthropic Claude claude-sonnet-4-6
     - Skip if ANTHROPIC_API_KEY not set
     - On any call failure: log and fall through to fallback
  2. Try OpenAI GPT-4o-mini
     - Skip if OPENAI_API_KEY not set
     - On any call failure: raise RuntimeError with details from both failures
  3. No retries — fail fast and use fallback

model_used values: "claude-sonnet-4-6" or "gpt-4o-mini"
"""

import os
import logging

logger = logging.getLogger(__name__)


def call_llm(system_prompt: str, user_prompt: str,
             max_tokens: int = 1500) -> dict:
    """
    Call Claude with GPT-4o-mini fallback.

    Returns:
        {"text": str, "model_used": str}

    Raises:
        RuntimeError: if both providers fail or both keys are missing.
    """
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    openai_key = os.environ.get("OPENAI_API_KEY", "")

    anthropic_error = None
    openai_error = None

    # --- Attempt 1: Anthropic Claude ---
    if anthropic_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            text = response.content[0].text
            logger.info("LLM call succeeded via claude-sonnet-4-6")
            return {"text": text, "model_used": "claude-sonnet-4-6"}

        except Exception as e:
            anthropic_error = str(e)
            logger.warning(f"Anthropic call failed, falling back to OpenAI: {anthropic_error}")
    else:
        anthropic_error = "ANTHROPIC_API_KEY not set"
        logger.info("ANTHROPIC_API_KEY not set — using OpenAI fallback")

    # --- Attempt 2: OpenAI GPT-4o-mini ---
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            text = response.choices[0].message.content
            logger.info("LLM call succeeded via gpt-4o-mini (fallback)")
            return {"text": text, "model_used": "gpt-4o-mini"}

        except Exception as e:
            openai_error = str(e)
            logger.error(f"OpenAI fallback also failed: {openai_error}")
    else:
        openai_error = "OPENAI_API_KEY not set"

    raise RuntimeError(
        f"Both LLM providers failed. "
        f"Anthropic: {anthropic_error}. "
        f"OpenAI: {openai_error}."
    )
