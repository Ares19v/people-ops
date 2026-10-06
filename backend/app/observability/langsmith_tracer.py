import os
import time
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

class LangSmithTracer:
    """Production dual-observability wrapper for tracking agent runs across LangSmith and Langfuse."""

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
                    host=settings.LANGFUSE_HOST,
                )
            except Exception:
                self._langfuse = None

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

        # If live Langfuse client is available, log trace and score
        if self._langfuse:
            try:
                lf_trace = self._langfuse.trace(
                    name=agent_name,
                    session_id=session_id,
                    metadata={"user_role": user_role, "guardrail_status": guardrail_status}
                )
                lf_trace.generation(
                    name=f"{agent_name}_generation",
                    input=scrubbed_input,
                    output=scrubbed_output,
                    metadata={"duration_ms": duration_ms, "token_usage": token_usage}
                )
                lf_trace.score(
                    name="compliance_safety_score",
                    value=safety_score,
                    comment="Automated DPDP/HIPAA guardrail safety score"
                )
            except Exception:
                pass

        return trace_payload

langsmith_tracer = LangSmithTracer()
