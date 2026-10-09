"""Production Observability, Cost Analytics, Sessions, Users, Alerts & Waterfall Tracer for Langfuse.
====================================================================================================
Handles:
1. Exact millisecond timing across hierarchical spans (Input Guardrails, Orchestrator, Subagent, Tool Selection, Tool Execution, Output Guardrails).
2. Token usage tracking & model-specific pricing/cost calculations across Gemini, GPT-4o, and Claude.
3. User & Session tracking for Langfuse 'Sessions' and 'Users' tabs (EMP-001, EMP-004, etc.).
4. Real-time Alerting and tags ('alert:prompt_injection', 'alert:pii_leakage', 'alert:high_latency') for the 'Alerts' tab.
5. Automated Evaluator scoring integration for the 'Evaluators' tab in Langfuse Cloud.
6. Clean ASCII/Unicode Waterfall formatting for UI and logs.
"""

import os
import time
from contextlib import contextmanager
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import json

from app.core.config import settings
from app.core.security import mask_all_pii
from app.observability.evaluators_and_alerts import evaluators_and_alerts_manager

try:
    from langsmith import Client as LangSmithClient
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False

try:
    from langfuse import Langfuse, propagate_attributes
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False


# Standard Model Pricing Table (Per 1 Million Tokens in USD)
MODEL_PRICING = {
    "gemini-2.5-flash": {"prompt": 0.075, "completion": 0.30},
    "gemini-1.5-flash": {"prompt": 0.075, "completion": 0.30},
    "gemini-1.5-pro": {"prompt": 1.25, "completion": 5.00},
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "gpt-4o": {"prompt": 2.50, "completion": 10.00},
    "claude-3-5-sonnet": {"prompt": 3.00, "completion": 15.00},
    "default": {"prompt": 0.10, "completion": 0.40}
}


def calculate_cost_usd(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculates estimated dollar cost based on model and token counts."""
    pricing = MODEL_PRICING.get(model_name.lower(), MODEL_PRICING["default"])
    input_cost = (prompt_tokens / 1_000_000.0) * pricing["prompt"]
    output_cost = (completion_tokens / 1_000_000.0) * pricing["completion"]
    return round(input_cost + output_cost, 6)


class _LocalTraceObservation:
    """Persistent local observation logger recording spans to disk."""
    def __init__(self, name: str, as_type: str, safe_input: Optional[str], metadata: Dict[str, Any], trace_dir: str):
        self.name = name
        self.as_type = as_type
        self.start_time = time.perf_counter()
        self.metadata = metadata
        self.trace_dir = trace_dir
        self.output = None
        self.duration_ms = 0.0

    def update(self, output: Optional[Any] = None, metadata: Optional[Dict[str, Any]] = None):
        if output is not None:
            self.output = str(output)[:300]
        if metadata:
            self.metadata.update(metadata)

    def close(self):
        self.duration_ms = (time.perf_counter() - self.start_time) * 1000
        try:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            trace_file = os.path.join(self.trace_dir, f"traces_{date_str}.jsonl")
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "span_name": self.name,
                "type": self.as_type,
                "duration_ms": round(self.duration_ms, 2),
                "metadata": self.metadata,
                "output_preview": self.output
            }
            with open(trace_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass


class LangSmithTracer:
    """Production observability wrapper for tracking agent runs across Langfuse, LangSmith, and local trace store."""

    def __init__(self):
        self._client = None
        self._langfuse = None
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self._trace_dir = os.path.join(base_dir, "data", "traces")
        os.makedirs(self._trace_dir, exist_ok=True)

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
    def trace_session(
        self,
        session_id: str,
        user_id: str,
        user_role: str = "EMPLOYEE",
        department: str = "Engineering",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        trace_name: str = "PeopleOps Enterprise Chat"
    ):
        """Context manager setting OpenTelemetry attributes so Sessions and Users are populated in Langfuse Cloud."""
        all_tags = list(tags or [])
        all_tags.extend(["production", f"dept:{department.lower()}", f"role:{user_role.lower()}"])
        meta = metadata or {}
        meta.update({"department": department, "user_role": user_role})

        if LANGFUSE_AVAILABLE and self._langfuse:
            try:
                with propagate_attributes(
                    user_id=user_id,
                    session_id=session_id,
                    tags=all_tags,
                    metadata=meta,
                    trace_name=trace_name
                ):
                    yield
                    return
            except Exception:
                pass
        yield

    @contextmanager
    def span(
        self,
        name: str,
        as_type: str = "span",
        input: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Context manager for hierarchical waterfall spans in Langfuse with local persistent fallback."""
        safe_input = mask_all_pii(str(input)) if input is not None else None
        meta = metadata or {}

        if self._langfuse:
            try:
                user_id = meta.get("user_id")
                session_id = meta.get("session_id")
                if user_id and session_id:
                    dept = meta.get("department", "engineering")
                    role = meta.get("user_role", "employee")
                    tags = ["production", f"dept:{dept.lower()}", f"role:{role.lower()}", f"user:{user_id.lower()}"]
                    with propagate_attributes(
                        user_id=user_id,
                        session_id=session_id,
                        tags=tags,
                        metadata=meta,
                        trace_name=f"PeopleOps Turn [{user_id}]" if name == "TOTAL ROUND-TRIP" else name
                    ):
                        with self._langfuse.start_as_current_observation(
                            name=name,
                            as_type=as_type,
                            input=safe_input,
                            metadata=meta,
                        ) as obs:
                            yield obs
                            return
                else:
                    with self._langfuse.start_as_current_observation(
                        name=name,
                        as_type=as_type,
                        input=safe_input,
                        metadata=meta,
                    ) as obs:
                        yield obs
                        return
            except Exception:
                pass

        # Persistent local trace span fallback
        local_obs = _LocalTraceObservation(name, as_type, safe_input, meta, self._trace_dir)
        try:
            yield local_obs
        finally:
            local_obs.close()

    def record_generation(
        self,
        name: str = "call_llm",
        model: str = "gemini-2.5-flash",
        input_text: str = "",
        output_text: str = "",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Records an LLM generation observation with token counts and calculates cost in USD."""
        cost_usd = calculate_cost_usd(model, prompt_tokens, completion_tokens)
        meta = metadata or {}
        meta["cost_usd"] = cost_usd
        meta["prompt_tokens"] = prompt_tokens
        meta["completion_tokens"] = completion_tokens
        meta["total_tokens"] = prompt_tokens + completion_tokens

        if self._langfuse:
            try:
                self._langfuse.start_observation(
                    name=name,
                    as_type="generation",
                    input=input_text[:500],
                    output=output_text[:500],
                    metadata=meta,
                    model=model,
                    usage_details={
                        "input": prompt_tokens,
                        "output": completion_tokens,
                        "total": prompt_tokens + completion_tokens
                    },
                    cost_details={
                        "total": cost_usd
                    }
                )
            except Exception:
                pass

        return cost_usd

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
        department: str = "Engineering",
        model_name: str = "gemini-2.5-flash"
    ):
        """Records a run trace with session, user, department cost analytics and alert tags."""
        scrubbed_input = mask_all_pii(raw_input)
        scrubbed_output = mask_all_pii(sanitized_output)

        prompt_tokens = token_usage.get("prompt_tokens", len(raw_input) // 4)
        completion_tokens = token_usage.get("completion_tokens", len(sanitized_output) // 4)
        total_tokens = prompt_tokens + completion_tokens
        cost_usd = calculate_cost_usd(model_name, prompt_tokens, completion_tokens)

        # Build dynamic tag set for Langfuse Filtering, Sessions, Users, and Alerts
        tags = [
            "production",
            f"dept:{department.lower()}",
            f"role:{user_role.lower()}",
            f"agent:{agent_name.lower()}"
        ]

        # Check and attach Alert Tags
        if guardrail_status == "INPUT_BLOCKED":
            tags.append("alert:prompt_injection")
            tags.append("alert:security_violation")
            evaluators_and_alerts_manager.trigger_alert(
                rule_name="Security: Prompt Injection or Jailbreak Attempt",
                severity="CRITICAL",
                session_id=session_id,
                user_id=user_id,
                message=f"Prompt injection blocked by NeMo Guardrails: {guardrail_tripped}",
                details={"raw_query_masked": scrubbed_input[:120]}
            )

        if safety_score < 1.0 or guardrail_tripped == "OUTPUT_PII_MASKED":
            tags.append("alert:pii_leakage")
            evaluators_and_alerts_manager.trigger_alert(
                rule_name="Compliance: PII Exposure / DPDP Breach",
                severity="CRITICAL",
                session_id=session_id,
                user_id=user_id,
                message="PII detected and masked by TokenVault scrubber",
                details={"session_id": session_id}
            )

        if duration_ms > 10000:
            tags.append("alert:high_latency")
            evaluators_and_alerts_manager.trigger_alert(
                rule_name="Performance: Latency SLA Exceeded (> 10s)",
                severity="WARNING",
                session_id=session_id,
                user_id=user_id,
                message=f"Execution took {duration_ms:.1f}ms, exceeding the 10,000ms SLA boundary",
                details={"latency_ms": duration_ms}
            )

        trace_payload = {
            "session_id": session_id,
            "user_id": user_id,
            "department": department,
            "user_role": user_role,
            "agent": agent_name,
            "input": scrubbed_input,
            "output": scrubbed_output,
            "guardrail_status": guardrail_status,
            "guardrail_tripped": guardrail_tripped,
            "duration_ms": duration_ms,
            "tags": tags,
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens
            },
            "cost_usd": cost_usd,
            "safety_score": safety_score,
            "timestamp": time.time()
        }

        # Flush to Langfuse
        self.flush()

        return trace_payload

    @staticmethod
    def format_waterfall_diagram(
        input_guardrails_ms: float,
        orchestrator_ms: float,
        subagent_ms: float,
        tool_selection_ms: float,
        tool_execution_ms: float,
        output_guardrails_ms: float,
        total_latency_sec: float,
        total_cost_usd: float
    ) -> str:
        """Renders the exact formatted ASCII/Unicode execution waterfall diagram requested."""
        return f"""
TOTAL ROUND-TRIP
|
Input
|
|-- Input Guardrails ----------- {int(input_guardrails_ms)} ms
|
|-- Orchestrator --------------- {int(orchestrator_ms)} ms
|   |
|   |-- Subagent --------------- {int(subagent_ms)} ms
|   |
|   \\-- Tool Selection --------- {int(tool_selection_ms)} ms
|       |
|       \\-- Tool Execution ----- {int(tool_execution_ms)} ms
|
\\-- Output Guardrails ---------- {int(output_guardrails_ms)} ms
|
v
Final Response

Total latency: {total_latency_sec:.2f} s
Total cost: ${total_cost_usd:.5f}
""".strip()


langsmith_tracer = LangSmithTracer()
