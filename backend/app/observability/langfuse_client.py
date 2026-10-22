"""Single, configured Langfuse client shared by every component.

Before this module the tracer, prompt service, judge, alerts and dataset service each built
their own `Langfuse(...)` with bare defaults. Everything now goes through `get_langfuse()` so
that environment, release, sampling and PII masking are applied consistently, tests never
write into the real project, and the client is flushed on shutdown.
"""
from __future__ import annotations

import logging
import re
import threading
from typing import Any, Optional

from app.core.config import settings
from app.core.security import mask_all_pii

logger = logging.getLogger(__name__)

try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    Langfuse = None  # type: ignore[assignment]
    LANGFUSE_AVAILABLE = False

_client: Optional[Any] = None
_initialised = False
_lock = threading.Lock()

_ENV_PATTERN = re.compile(r"[^a-z0-9_-]")


def langfuse_environment() -> str:
    """Langfuse environment name for this deployment (lowercase, [a-z0-9_-], max 40, not 'langfuse*')."""
    env = _ENV_PATTERN.sub("-", (settings.ENVIRONMENT or "development").lower()).strip("-")[:40]
    if not env or env.startswith("langfuse"):
        return "development"
    return env


def is_enabled() -> bool:
    """Tracing is on only with keys present, the flag set, and never under the test environment."""
    return bool(
        LANGFUSE_AVAILABLE
        and settings.LANGFUSE_ENABLED
        and settings.LANGFUSE_PUBLIC_KEY
        and settings.LANGFUSE_SECRET_KEY
        and (settings.ENVIRONMENT or "").lower() != "testing"
    )


def _mask(data: Any = None, **_: Any) -> Any:
    """Scrub PII from anything Langfuse is about to export (inputs, outputs, metadata)."""
    if isinstance(data, str):
        return mask_all_pii(data)
    if isinstance(data, dict):
        return {k: _mask(v) for k, v in data.items()}
    if isinstance(data, (list, tuple)):
        return type(data)(_mask(v) for v in data)
    return data


def get_langfuse() -> Optional[Any]:
    """Return the shared client, or None when tracing is disabled / unavailable."""
    global _client, _initialised
    if _initialised:
        return _client
    with _lock:
        if _initialised:
            return _client
        if is_enabled():
            try:
                _client = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_BASE_URL or settings.LANGFUSE_HOST,
                    environment=langfuse_environment(),
                    release=settings.LANGFUSE_RELEASE or settings.APP_VERSION,
                    sample_rate=settings.LANGFUSE_SAMPLE_RATE,
                    mask=_mask,
                    timeout=10,
                )
                logger.info(
                    "Langfuse client ready (environment=%s, release=%s, sample_rate=%s)",
                    langfuse_environment(), settings.LANGFUSE_RELEASE or settings.APP_VERSION,
                    settings.LANGFUSE_SAMPLE_RATE,
                )
            except Exception as exc:
                logger.warning("Langfuse client could not be initialised; tracing disabled: %s", exc)
                _client = None
        else:
            logger.info("Langfuse tracing disabled (missing keys, LANGFUSE_ENABLED=false, or testing environment)")
        _initialised = True
        return _client


def current_trace_id() -> Optional[str]:
    """Trace id of the active observation, or None outside a trace / when disabled."""
    client = get_langfuse()
    if client is None:
        return None
    try:
        return client.get_current_trace_id()
    except Exception:
        return None


def trace_url(trace_id: Optional[str]) -> Optional[str]:
    client = get_langfuse()
    if client is None or not trace_id:
        return None
    try:
        return client.get_trace_url(trace_id=trace_id)
    except Exception:
        return None


def flush() -> None:
    client = get_langfuse() if _initialised else None
    if client is not None:
        try:
            client.flush()
        except Exception as exc:
            logger.debug("Langfuse flush failed: %s", exc)


def shutdown() -> None:
    """Flush pending events and stop background threads (call once on application shutdown)."""
    global _client, _initialised
    with _lock:
        client, _client, _initialised = _client, None, False
    if client is not None:
        try:
            client.shutdown()
        except Exception as exc:
            logger.debug("Langfuse shutdown failed: %s", exc)


def reset_for_tests() -> None:
    """Drop the cached client so the next get_langfuse() re-reads settings."""
    global _client, _initialised
    with _lock:
        _client, _initialised = None, False
