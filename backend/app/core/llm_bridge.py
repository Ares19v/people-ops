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
_active_groq_model: Optional[str] = None
_exhausted_groq_models: set[str] = set()

GROQ_FALLBACK_MODELS = [
    "groq/openai/gpt-oss-120b",
    "groq/openai/gpt-oss-20b",
    "groq/qwen/qwen3.8-27b",
]


def get_active_groq_model() -> str:
    global _active_groq_model
    if _active_groq_model is None or _active_groq_model in _exhausted_groq_models:
        preferred = settings.GROQ_MODEL
        if preferred not in _exhausted_groq_models:
            _active_groq_model = preferred
        else:
            avail = [m for m in GROQ_FALLBACK_MODELS if m not in _exhausted_groq_models]
            _active_groq_model = avail[0] if avail else GROQ_FALLBACK_MODELS[0]
    return _active_groq_model


def switch_groq_fallback_model(failed_model: Optional[str] = None) -> str:
    """Switch active Groq model to the next available model in GROQ_FALLBACK_MODELS."""
    global _active_groq_model
    current = failed_model or get_active_groq_model()
    if current:
        _exhausted_groq_models.add(current)
    candidates = [m for m in GROQ_FALLBACK_MODELS if m not in _exhausted_groq_models]
    if not candidates:
        _exhausted_groq_models.clear()
        candidates = [m for m in GROQ_FALLBACK_MODELS if m != current]
    if candidates:
        next_model = candidates[0]
        _active_groq_model = next_model
        logger.warning("Groq model '%s' rate-limited or failed; switched active model to '%s'", current, next_model)
    return get_active_groq_model()


def _get_gemini_key() -> Optional[str]:
    from dotenv import dotenv_values
    for path in [".env", "backend/.env", "../.env"]:
        if os.path.exists(path):
            vals = dotenv_values(path)
            k = vals.get("GEMINI_API_KEY")
            if k and not k.startswith("AIzaSyDB0j"):
                return k
    return settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")


def _get_groq_key() -> Optional[str]:
    from dotenv import dotenv_values
    for path in [".env", "backend/.env", "../.env"]:
        if os.path.exists(path):
            vals = dotenv_values(path)
            k = vals.get("GROQ_API_KEY") or vals.get("OPENAI_API_KEY")
            if k and k.startswith("gsk_"):
                return k
    return (
        getattr(settings, "GROQ_API_KEY", None)
        or (settings.OPENAI_API_KEY if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.startswith("gsk_") else None)
        or os.environ.get("GROQ_API_KEY")
        or (os.environ.get("OPENAI_API_KEY") if (os.environ.get("OPENAI_API_KEY") or "").startswith("gsk_") else None)
    )


def _get_openai_key() -> Optional[str]:
    k = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
    if k and k.startswith("gsk_"):
        return None  # Routed to Groq instead
    return k


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
      1. Explicit "groq" or Groq key present -> use Groq via LiteLLM
      2. Explicit "openai" -> use OpenAI via LiteLLM
      3. "gemini" -> test Gemini; fallback if unavailable
      4. If no valid keys, fall back to "mock" for zero-crash local development
    """
    global _resolved_provider
    if _resolved_provider is not None:
        return _resolved_provider

    groq_key = _get_groq_key()
    openai_key = _get_openai_key()
    gemini_key = _get_gemini_key()

    if groq_key and (settings.LLM_PROVIDER.lower() in ("groq", "openai") or not openai_key):
        _resolved_provider = "groq"
        logger.info("LLM Provider resolved: Groq (%s)", get_active_groq_model())
        return _resolved_provider

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
    elif groq_key:
        _resolved_provider = "groq"
        logger.info("Falling back to Groq via LiteLLM (%s)", get_active_groq_model())
    elif settings.MOCK_LLM_ENABLED:
        _resolved_provider = "mock"
        logger.info("No external LLM keys detected — operating in MOCK_LLM mode")
    else:
        _resolved_provider = "gemini"
        logger.warning("Defaulting to Gemini; API calls will surface live provider status")

    return _resolved_provider


def get_llm_model(model_override: Optional[str] = None) -> Any:
    """
    Return model representation for Google ADK Agents.
    - "groq": LiteLlm(model="groq/llama-3.3-70b-versatile")
    - "gemini": Bare string model name ("gemini-2.5-flash")
    - "openai": LiteLlm(model="gpt-4o")
    - "mock": Fallback string
    """
    provider = resolve_llm_provider()

    if provider == "groq":
        groq_key = _get_groq_key()
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
        os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
        os.environ.setdefault("LITELLM_DROP_PARAMS", "True")
        target_model = model_override or get_active_groq_model()
        try:
            from google.adk.models.lite_llm import LiteLlm
            return LiteLlm(model=target_model)
        except Exception as e:
            logger.warning("Could not initialize LiteLlm for Groq (%s), using model string", e)
            return target_model

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
    """Execute text completion through whichever provider was resolved, with automatic model failover."""
    provider = resolve_llm_provider()

    if provider == "groq":
        groq_key = _get_groq_key()
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
        import litellm

        fast_default = "groq/llama-3.1-8b-instant"
        models_to_try = [m for m in ([fast_default] + GROQ_FALLBACK_MODELS) if m not in _exhausted_groq_models]
        if not models_to_try:
            models_to_try = list(GROQ_FALLBACK_MODELS)
        # Deduplicate while preserving order
        seen = set()
        ordered_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

        last_exc = None
        for model_name in ordered_models:
            try:
                resp = await litellm.acompletion(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=1024,
                )
                return (resp.choices[0].message.content or "").strip()
            except Exception as exc:
                last_exc = exc
                _exhausted_groq_models.add(model_name)
                logger.warning("Groq summary completion failed on '%s' (%s), trying next fallback model", model_name, exc)
        if last_exc:
            raise last_exc

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
