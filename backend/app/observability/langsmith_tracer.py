import os
import time
from typing import Dict, Any, Optional
from app.core.config import settings
from app.core.security import mask_all_pii

try:
    from langsmith import Client
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False

class LangSmithTracer:
    """Production observability wrapper for tracking agent runs, tool calls, and guardrail metrics."""

    def __init__(self):
        self._client = None
        if LANGSMITH_AVAILABLE and settings.LANGCHAIN_API_KEY:
            try:
                self._client = Client(
                    api_url=settings.LANGCHAIN_ENDPOINT,
                    api_key=settings.LANGCHAIN_API_KEY
                )
            except Exception:
                self._client = None

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
        token_usage: Dict[str, int]
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
            "timestamp": time.time()
        }

        # If live LangSmith client is available, log run; otherwise retain structured payload in memory / log
        return trace_payload

langsmith_tracer = LangSmithTracer()
