"""ADK-native evaluation support for the PeopleOps agent fleet (Google ADK 2.x).

Google ADK ships its own evaluators and an Eval tab in `adk web`. This module lets both run against the
SAME agent object the backend uses (`hr_root_orchestrator`):

* `identity_shim` / `install_identity_shim` - the production pipeline puts an "[Active Employee ...]" header
  and the current time on every message so tools receive a real `user_id`. ADK Web and ADK evals send bare
  questions, so the same text is added to the model's system instructions instead.
* `run_adk_evaluation` - drives an ADK eval set through ADK's own `LocalEvalService` (the same service
  behind `adk eval` and the Eval tab) with an ADK criteria config, and returns per-case results for every
  evaluator: tool trajectory, response match, semantic final-response match, rubric-based response and tool
  quality, hallucinations (plus safety and the multi-turn criteria when configured).
"""
from __future__ import annotations

import contextlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

from app.core.employee_context import build_employee_header, build_time_context

logger = logging.getLogger(__name__)

ADK_APP_NAME = "peopleops"
DEFAULT_EVAL_USER_ID = "EMP-004"
EFFICIENCY_METRICS = ("token_usage_v1", "tool_call_count_v1", "inference_call_count_v1", "invocation_duration_v1")
MISSING_EVAL_DEPENDENCIES = (
    "ADK's evaluators need the evaluation extras. Install them with: pip install -r backend/requirements.txt"
)


# ── identity shim ─────────────────────────────────────────────────────────────

def _iter_agents(agent: Any) -> Iterator[Any]:
    yield agent
    for sub in getattr(agent, "sub_agents", None) or []:
        yield from _iter_agents(sub)


def _identity_callback(callback_context: Any, llm_request: Any):
    state = getattr(callback_context, "state", None)
    user_id = (state.get("user_id") if state is not None else None) or DEFAULT_EVAL_USER_ID
    llm_request.append_instructions([build_employee_header(user_id), build_time_context()])
    return None  # continue to the model


@contextlib.contextmanager
def identity_shim(root_agent: Any) -> Iterator[None]:
    """Temporarily give every agent in the tree the active-employee context, then restore."""
    saved = [(agent, getattr(agent, "before_model_callback", None)) for agent in _iter_agents(root_agent)]
    for agent, _ in saved:
        agent.before_model_callback = _identity_callback
    try:
        yield
    finally:
        for agent, previous in saved:
            agent.before_model_callback = previous


def _identity_and_prompt_refresh_callback(callback_context: Any, llm_request: Any):
    # Same hot-reload the pipeline does per request, so prompts edited in Langfuse reach ADK Web too
    # (get_prompt is cached for a few seconds, so this is cheap).
    try:
        from app.agents.adk_fleet import sync_agent_instructions

        sync_agent_instructions()
    except Exception as exc:  # never break a chat turn over a prompt refresh
        logger.debug("Prompt refresh skipped: %s", exc)
    return _identity_callback(callback_context, llm_request)


def install_identity_shim(root_agent: Any, refresh_prompts: bool = False) -> None:
    """Permanent variant for the dedicated ADK Web process (optionally hot-reloading Langfuse prompts)."""
    callback = _identity_and_prompt_refresh_callback if refresh_prompts else _identity_callback
    for agent in _iter_agents(root_agent):
        agent.before_model_callback = callback


# ── results ───────────────────────────────────────────────────────────────────

@dataclass
class AdkCase:
    test_id: str
    query: str
    expected_tool_use: List[Dict[str, Any]]
    reference: str


@dataclass
class AdkCaseResult:
    test_id: str
    status: Optional[str] = None                       # ADK's final status: PASSED / FAILED / NOT_EVALUATED
    response: Optional[str] = None
    actual_tool_use: List[Dict[str, Any]] = field(default_factory=list)
    expected_tool_use: List[Dict[str, Any]] = field(default_factory=list)
    # metric name -> {"score", "status", "threshold", "rubrics": [{"rubric_id", "score", "rationale"}]}
    metrics: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    efficiency: Dict[str, Any] = field(default_factory=dict)  # informational: tokens, tool calls, duration
    latency_ms: Optional[float] = None
    session_id: Optional[str] = None
    error: Optional[str] = None

    def score(self, metric: str) -> Optional[float]:
        return (self.metrics.get(metric) or {}).get("score")

    @property
    def passed(self) -> Optional[bool]:
        return None if self.status is None else self.status == "PASSED"


def _text_of(content: Any) -> str:
    parts = getattr(content, "parts", None) or []
    return "".join(getattr(p, "text", None) or "" for p in parts).strip()


def _tool_calls_of(invocation: Any) -> List[Dict[str, Any]]:
    """Tool calls of an ADK Invocation, whichever intermediate-data flavour it carries."""
    data = getattr(invocation, "intermediate_data", None)
    if data is None:
        return []
    uses = getattr(data, "tool_uses", None)
    if uses is not None:
        return [{"tool_name": u.name, "tool_input": dict(u.args or {})} for u in uses]
    calls: List[Dict[str, Any]] = []
    for event in getattr(data, "invocation_events", None) or []:
        for part in getattr(getattr(event, "content", None), "parts", None) or []:
            call = getattr(part, "function_call", None)
            if call is not None:
                calls.append({"tool_name": call.name, "tool_input": dict(call.args or {})})
    return calls


def _metric_entry(result: Any) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "score": result.score,
        "status": result.eval_status.name,
        "threshold": getattr(result, "threshold", None),
    }
    rubric_scores = getattr(getattr(result, "details", None), "rubric_scores", None) or []
    if rubric_scores:
        entry["rubrics"] = [
            {"rubric_id": r.rubric_id, "score": r.score, "rationale": r.rationale} for r in rubric_scores
        ]
    return entry


def _convert(case_result: Any, expected: List[Dict[str, Any]]) -> AdkCaseResult:
    result = AdkCaseResult(
        test_id=case_result.eval_id,
        status=case_result.final_eval_status.name,
        expected_tool_use=expected,
        session_id=case_result.session_id,
    )
    for metric_result in case_result.overall_eval_metric_results:
        entry = _metric_entry(metric_result)
        if metric_result.metric_name in EFFICIENCY_METRICS:
            result.efficiency[metric_result.metric_name] = entry["score"]
        else:
            result.metrics[metric_result.metric_name] = entry
    per_invocation = case_result.eval_metric_result_per_invocation
    if per_invocation:
        actual = per_invocation[0].actual_invocation
        result.response = _text_of(actual.final_response) or None
        result.actual_tool_use = _tool_calls_of(actual)
        if getattr(actual, "duration", None):
            result.latency_ms = round(actual.duration * 1000, 1)
    if not (result.response or "").strip():
        # A provider failure (rate limit, auth) surfaces as "no final answer"; report it, never score it as wrong.
        result.error = "agent produced no final response (LLM provider error or rate limit?)"
    return result


# ── running an eval set through ADK's own evaluation service ──────────────────

def _default_root_agent() -> Any:
    from app.agents.adk_fleet import hr_root_orchestrator

    return hr_root_orchestrator


async def run_adk_evaluation(
    eval_set: Dict[str, Any],
    eval_config: Dict[str, Any],
    *,
    root_agent: Any = None,
    test_ids: Optional[List[str]] = None,
) -> List[AdkCaseResult]:
    """Run an ADK eval set with ADK's own evaluators and return one result per case.

    `eval_set` and `eval_config` are the JSON documents ADK loads (see `adk_expectations.to_eval_set` and
    `build_eval_config`). Judge-based criteria call the judge model named in the config.
    """
    try:
        from google.adk.evaluation.base_eval_service import (
            EvaluateConfig, EvaluateRequest, InferenceConfig, InferenceRequest, InferenceStatus,
        )
        from google.adk.evaluation.eval_config import EvalConfig, get_eval_metrics_from_config
        from google.adk.evaluation.eval_set import EvalSet
        from google.adk.evaluation.in_memory_eval_sets_manager import InMemoryEvalSetsManager
        from google.adk.evaluation.local_eval_service import LocalEvalService
        from google.adk.evaluation.metric_evaluator_registry import register_custom_metrics_from_config
        from google.adk.evaluation.simulation.user_simulator_provider import UserSimulatorProvider
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"{MISSING_EVAL_DEPENDENCIES} ({exc})") from exc

    from app.core.llm_bridge import export_provider_keys_to_env

    export_provider_keys_to_env()  # ADK builds judge models from names, using the process environment
    parsed_set = EvalSet.model_validate(eval_set)
    config = EvalConfig.model_validate(eval_config)
    metrics = get_eval_metrics_from_config(config)
    expected_by_id = {
        case.eval_id: [
            {"tool_name": u.name, "tool_input": dict(u.args or {})}
            for u in (case.conversation[0].intermediate_data.tool_uses if case.conversation and case.conversation[0].intermediate_data else [])
        ]
        for case in parsed_set.eval_cases
    }

    manager = InMemoryEvalSetsManager()
    manager.create_eval_set(app_name=ADK_APP_NAME, eval_set_id=parsed_set.eval_set_id)
    for case in parsed_set.eval_cases:
        manager.add_eval_case(app_name=ADK_APP_NAME, eval_set_id=parsed_set.eval_set_id, eval_case=case)

    root = root_agent or _default_root_agent()
    service = LocalEvalService(
        root_agent=root,
        eval_sets_manager=manager,
        user_simulator_provider=UserSimulatorProvider(user_simulator_config=config.user_simulator_config),
        metric_evaluator_registry=register_custom_metrics_from_config(config),
    )

    started = time.perf_counter()
    results: Dict[str, AdkCaseResult] = {}
    with identity_shim(root):
        inferences = []
        request = InferenceRequest(
            app_name=ADK_APP_NAME,
            eval_set_id=parsed_set.eval_set_id,
            eval_case_ids=test_ids or [],
            inference_config=InferenceConfig(use_live=False),
        )
        async for inference in service.perform_inference(inference_request=request):
            if inference.status == InferenceStatus.SUCCESS:
                inferences.append(inference)
            else:
                results[inference.eval_case_id] = AdkCaseResult(
                    test_id=inference.eval_case_id,
                    expected_tool_use=expected_by_id.get(inference.eval_case_id, []),
                    error=f"inference failed: {inference.error_message}"[:300],
                )
        evaluate_request = EvaluateRequest(
            inference_results=inferences, evaluate_config=EvaluateConfig(eval_metrics=metrics)
        )
        async for case_result in service.evaluate(evaluate_request=evaluate_request):
            results[case_result.eval_id] = _convert(case_result, expected_by_id.get(case_result.eval_id, []))

    elapsed = round((time.perf_counter() - started) * 1000, 1)
    ordered = [results[c.eval_id] for c in parsed_set.eval_cases if c.eval_id in results]
    for item in ordered:
        item.latency_ms = item.latency_ms or elapsed / max(1, len(ordered))
    return ordered
