import os
import time
from contextlib import contextmanager
from typing import Dict, Any, Optional
from app.core.config import settings
from app.core.security import mask_all_pii

try:
    from langsmith import Client as LangSmithClient
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False

try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False


class _DummyObservation:
    """Safe fallback observation that swallows updates when Langfuse is offline."""
    def update(self, *args, **kwargs):
        pass


class LangSmithTracer:
    """Production dual-observability wrapper for tracking agent runs across LangSmith and Langfuse.
    
    Supports hierarchical waterfall spans:
      TOTAL ROUND-TRIP
      ├── Input Guardrails
      ├── Orchestrator
      │   ├── Subagent
      │   └── Tool Selection
      │       └── Tool Execution
      └── Output Guardrails
    """

    def __init__(self):
        self._client = None
        self._langfuse = None

        if LANGSMITH_AVAILABLE and settings.LANGCHAIN_API_KEY:
            try:
                self._client = LangSmithClient(
                    api_url=settings.LANGCHAIN_ENDPOINT,
                    api_key=settings.LANGCHAIN_API_KEY
                )
            except Exception:
                self._client = None

        if LANGFUSE_AVAILABLE and settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            try:
                self._langfuse = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_BASE_URL or settings.LANGFUSE_HOST,
                )
            except Exception:
                self._langfuse = None

    @contextmanager
    def span(
        self,
        name: str,
        as_type: str = "span",
        input: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Context manager for hierarchical waterfall spans in Langfuse."""
        if self._langfuse:
            try:
                # Mask sensitive PII before sending to telemetry
                safe_input = mask_all_pii(str(input)) if input is not None else None
                with self._langfuse.start_as_current_observation(
                    name=name,
                    as_type=as_type,
                    input=safe_input,
                    metadata=metadata or {},
                ) as obs:
                    yield obs
                    return
            except Exception:
                pass
        yield _DummyObservation()

    def score(self, name: str, value: float, comment: Optional[str] = None):
        """Attach a score to the active trace in Langfuse."""
        if self._langfuse:
            try:
                self._langfuse.score_current_trace(
                    name=name,
                    value=value,
                    comment=comment,
                )
            except Exception:
                pass

    def flush(self):
        """Flush all pending observations to Langfuse cloud immediately."""
        if self._langfuse:
            try:
                self._langfuse.flush()
            except Exception:
                pass

    def trace_agent_run(
        self,
        session_id: str,
        user_id: str,
        user_role: str,
        agent_name: str,
        raw_input: str,
        sanitized_output: str,
        guardrail_status: str,
        guardrail_tripped: Optional[str],
        duration_ms: float,
        token_usage: Dict[str, int],
        safety_score: float = 1.0,
    ):
        """Records a run trace, ensuring all PII is scrubbed before logging."""
        scrubbed_input = mask_all_pii(raw_input)
        scrubbed_output = mask_all_pii(sanitized_output)

        trace_payload = {
            "session_id": session_id,
            "user_id": user_id,
            "user_role": user_role,
            "agent": agent_name,
            "input": scrubbed_input,
            "output": scrubbed_output,
            "guardrail_status": guardrail_status,
            "guardrail_tripped": guardrail_tripped,
            "duration_ms": duration_ms,
            "token_usage": token_usage,
            "safety_score": safety_score,
            "timestamp": time.time()
        }

        # Flush to Langfuse if available
        self.flush()

        return trace_payload


langsmith_tracer = LangSmithTracer()

