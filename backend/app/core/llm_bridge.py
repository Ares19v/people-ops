"""
PeopleOps — Multi-Model Provider Bridge for Google ADK & LiteLLM
================================================================
Provides:
  • get_llm_model()        — Returns model identifier / LiteLlm instance for ADK agents
  • resolve_llm_provider() — Automatic failover probe between Gemini, OpenAI, and Mock
  • generate_summary()     — Non-agent completion helper
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_resolved_provider: Optional[str] = None


def _get_gemini_key() -> Optional[str]:
    return settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _get_openai_key() -> Optional[str]:
    return settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")


def _probe_gemini() -> bool:
    """Return True if a minimal Gemini generation test passes."""
    key = _get_gemini_key()
    if not key:
        return False
    try:
        from google import genai
        client = genai.Client(api_key=key)
        # Test minimal token generation
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents="ok",
        )
        return bool(response and response.text)
    except Exception as exc:
        logger.warning("Gemini key probe failed (%s: %s)", type(exc).__name__, exc)
        return False


def resolve_llm_provider() -> str:
    """
    Decide which provider to use with probe-based fallback.
      1. Explicit "openai" -> use OpenAI via LiteLLM
      2. "gemini" -> test Gemini; fallback to OpenAI if key provided
      3. If no valid keys, fall back to "mock" for zero-crash local development
    """
    global _resolved_provider
    if _resolved_provider is not None:
        return _resolved_provider

    openai_key = _get_openai_key()
    gemini_key = _get_gemini_key()

    if settings.LLM_PROVIDER.lower() == "openai" and openai_key:
        _resolved_provider = "openai"
        logger.info("LLM Provider resolved: OpenAI (explicit)")
        return _resolved_provider

    if _probe_gemini():
        _resolved_provider = "gemini"
        logger.info("LLM Provider resolved: Gemini (%s)", settings.GEMINI_MODEL)
    elif openai_key:
        _resolved_provider = "openai"
        logger.warning("Gemini unavailable/unconfigured — falling back to OpenAI via LiteLLM")
    elif settings.MOCK_LLM_ENABLED:
        _resolved_provider = "mock"
        logger.info("No external LLM keys detected — operating in MOCK_LLM mode")
    else:
        _resolved_provider = "gemini"
        logger.warning("Defaulting to Gemini; API calls will surface live provider status")

    return _resolved_provider


def get_llm_model() -> Any:
    """
    Return model representation for Google ADK Agents.
    - "gemini": Bare string model name ("gemini-2.5-flash")
    - "openai": LiteLlm(model="gpt-4o")
    - "mock": Fallback string
    """
    provider = resolve_llm_provider()

    if provider == "openai":
        openai_key = _get_openai_key()
        if openai_key:
            os.environ.setdefault("OPENAI_API_KEY", openai_key)
        os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
        os.environ.setdefault("LITELLM_DROP_PARAMS", "True")
        try:
            from google.adk.models.lite_llm import LiteLlm
            return LiteLlm(model=settings.OPENAI_MODEL)
        except Exception as e:
            logger.warning("Could not initialize LiteLlm (%s), using model string", e)
            return settings.OPENAI_MODEL

    gemini_key = _get_gemini_key()
    if gemini_key:
        os.environ.setdefault("GOOGLE_API_KEY", gemini_key)
        os.environ.setdefault("GEMINI_API_KEY", gemini_key)

    return settings.GEMINI_MODEL


async def generate_summary(prompt: str) -> str:
    """Execute text completion through whichever provider was resolved."""
    provider = resolve_llm_provider()

    if provider == "openai":
        openai_key = _get_openai_key()
        if openai_key:
            os.environ.setdefault("OPENAI_API_KEY", openai_key)
        import litellm
        resp = await litellm.acompletion(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1024,
        )
        return (resp.choices[0].message.content or "").strip()

    if provider == "gemini":
        gemini_key = _get_gemini_key()
        if gemini_key:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            resp = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
            )
            return (resp.text or "").strip()

    return f"[MOCK SUMMARY] Processed: {prompt[:80]}..."
