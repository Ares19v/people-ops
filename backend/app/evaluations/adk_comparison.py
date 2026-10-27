"""Side-by-side comparison of the two ways of evaluating the same agent fleet on the same golden cases.

* ADK leg   - the agent fleet alone, driven and scored by Google ADK's own evaluators: tool trajectory,
              response match (ROUGE-1), final_response_match_v2 (LLM judge vs the reference), rubric-based
              response and tool-use quality, and hallucinations. This is what the Eval tab in ADK Web runs.
* Langfuse leg - the full production pipeline (guardrails, PII redaction, memory, ADK fleet, output clean-up)
              scored by the judge, recorded as a Langfuse experiment run.

The two are not interchangeable: ADK checks HOW the agent got its answer (which tools, with which arguments)
and how close the text is to a reference; Langfuse's judge checks WHETHER the answer is right, safe and
compliant. The report lines them up per case, shows where they disagree, and attaches the ADK aggregates to
the Langfuse run as run-level scores so both can be read in the Langfuse UI.
"""
from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.evaluations.adk_expectations import EXPECTATIONS, adk_cases, build_eval_config, to_eval_set
from app.evaluations.adk_support import AdkCaseResult, run_adk_evaluation
from app.evaluations.golden_dataset_25 import GOLDEN_BENCHMARK_25
from app.evaluations.llm_judge_service import HEURISTIC_JUDGE, resolve_default_judge

logger = logging.getLogger(__name__)

ADK_METRICS = (
    "tool_trajectory_avg_score", "response_match_score", "final_response_match_v2",
    "rubric_based_final_response_quality_v1", "rubric_based_tool_use_quality_v1", "hallucinations_v1",
)

METRIC_GUIDE = {
    "adk.tool_trajectory_avg_score": "ADK. 1.0 only if the ordered tool calls (names AND arguments) equal the expectation. Catches wrong routing, missing, extra or duplicated tool calls; fails on harmless rewording of free-text arguments.",
    "adk.response_match_score": "ADK. ROUGE-1 F-measure against the reference text: word overlap, not correctness.",
    "adk.final_response_match_v2": "ADK. An LLM judge decides whether the answer is semantically equivalent to the reference.",
    "adk.rubric_based_final_response_quality_v1": "ADK. An LLM judge scores the answer against a yes/no rubric (answers the question, no invented facts, forbidden content, ...).",
    "adk.rubric_based_tool_use_quality_v1": "ADK. An LLM judge scores the tool use against a rubric (right agent, employee id not name, no duplicate calls, ...).",
    "adk.hallucinations_v1": "ADK. Share of the answer's claims supported by the tool results and instructions.",
    "langfuse.overall_score": "Judge score 0-1 (groundedness, helpfulness, statutory compliance, safety), on the full pipeline's answer.",
    "langfuse.passed": "overall >= 0.70 and safety >= 0.80.",
}

_last_comparison: Dict[str, Any] = {"status": "never_run"}


def last_comparison() -> Dict[str, Any]:
    return _last_comparison


def set_last_comparison(value: Dict[str, Any]) -> None:
    global _last_comparison
    _last_comparison = value


def _pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return round(sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / (var_x * var_y) ** 0.5, 3)


def _mean(values: List[float]) -> Optional[float]:
    return round(sum(values) / len(values), 3) if values else None


def _paired(scored: List[Dict[str, Any]], metric: str):
    """Langfuse overall scores and one ADK metric, for the cases where both exist."""
    pairs = [(r["langfuse"]["overall_score"], r["adk"]["scores"][metric]) for r in scored if r["adk"]["scores"].get(metric) is not None]
    return [p[0] for p in pairs], [p[1] for p in pairs]


def _agreement(langfuse_pass: Optional[bool], adk_pass: Optional[bool]) -> str:
    if langfuse_pass is None or adk_pass is None:
        return "not_comparable"
    if langfuse_pass and adk_pass:
        return "both_pass"
    if not langfuse_pass and not adk_pass:
        return "both_fail"
    return "langfuse_only" if langfuse_pass else "adk_only"


def build_report(
    cases: List[Any],
    adk_results: List[AdkCaseResult],
    langfuse_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Pure function: merge the two legs into per-case rows and aggregates (unit-tested without any LLM)."""
    prompt_to_id = {tc.prompt: tc.test_id for tc in GOLDEN_BENCHMARK_25}
    category = {tc.test_id: tc.category for tc in GOLDEN_BENCHMARK_25}
    adk_by_id = {r.test_id: r for r in adk_results}
    lf_by_id = {prompt_to_id.get(item.get("prompt")): item for item in langfuse_items if prompt_to_id.get(item.get("prompt"))}

    rows: List[Dict[str, Any]] = []
    for case in cases:
        adk = adk_by_id.get(case.test_id)
        lf = lf_by_id.get(case.test_id)
        expectation = EXPECTATIONS[case.test_id]

        adk_row = None
        adk_pass: Optional[bool] = None
        if adk is not None:
            if adk.error:
                adk_row = {"error": adk.error, "latency_ms": adk.latency_ms}
            else:
                adk_pass = adk.passed
                adk_row = {
                    "scores": {name: adk.score(name) for name in adk.metrics},
                    "statuses": {name: entry["status"] for name, entry in adk.metrics.items()},
                    "failed_rubrics": [
                        f"{name}:{rubric['rubric_id']}"
                        for name, entry in adk.metrics.items()
                        for rubric in entry.get("rubrics", [])
                        if (rubric["score"] or 0.0) < 1.0
                    ],
                    "tool_trajectory_avg_score": adk.score("tool_trajectory_avg_score"),
                    "response_match_score": round(adk.score("response_match_score") or 0.0, 3),
                    "passed": adk_pass,
                    "actual_tools": [c["tool_name"] for c in adk.actual_tool_use],
                    "expected_tools": [c["tool_name"] for c in adk.expected_tool_use],
                    "efficiency": adk.efficiency,
                    "latency_ms": adk.latency_ms,
                }

        lf_row = None
        lf_pass: Optional[bool] = None
        if lf is not None:
            if lf.get("error"):
                lf_row = {"error": lf["error"]}
            else:
                lf_pass = bool(lf.get("passed"))
                lf_row = {
                    "overall_score": lf.get("overall_score"),
                    "passed": lf_pass,
                    "agent_routed": lf.get("agent_routed"),
                    "latency_ms": lf.get("latency_ms"),
                    "metrics": lf.get("evaluations"),
                }

        rows.append({
            "test_id": case.test_id,
            "category": category.get(case.test_id),
            "deterministic_arguments": expectation.deterministic,
            "mutating": expectation.mutating,
            "adk": adk_row,
            "langfuse": lf_row,
            "agreement": _agreement(lf_pass, adk_pass),
        })

    scored = [r for r in rows if r["adk"] and "error" not in r["adk"] and r["langfuse"] and "error" not in r["langfuse"]]
    lf_scores = [r["langfuse"]["overall_score"] for r in scored]
    rouge = [r["adk"]["response_match_score"] for r in scored]
    agreement_counts: Dict[str, int] = {}
    for r in rows:
        agreement_counts[r["agreement"]] = agreement_counts.get(r["agreement"], 0) + 1

    adk_ok = [r["adk"] for r in rows if r["adk"] and "error" not in r["adk"]]
    deterministic_ok = [r["adk"] for r in rows if r["adk"] and "error" not in r["adk"] and r["deterministic_arguments"]]
    lf_ok = [r["langfuse"] for r in rows if r["langfuse"] and "error" not in r["langfuse"]]
    aggregate = {
        "cases": len(rows),
        "adk": {
            "evaluated": len(adk_ok),
            "errors": sum(1 for r in rows if r["adk"] and "error" in r["adk"]),
            "metrics": {
                name: _mean([a["scores"][name] for a in adk_ok if a["scores"].get(name) is not None])
                for name in ADK_METRICS
            },
            "tool_trajectory_avg_score": _mean([a["tool_trajectory_avg_score"] for a in adk_ok]),
            "tool_trajectory_avg_score_deterministic_cases": _mean([a["tool_trajectory_avg_score"] for a in deterministic_ok]),
            "response_match_score": _mean([a["response_match_score"] for a in adk_ok]),
            "pass_rate": _mean([1.0 if a["passed"] else 0.0 for a in adk_ok]),
            "total_tokens": sum((a["efficiency"] or {}).get("token_usage_v1") or 0 for a in adk_ok),
        },
        "langfuse": {
            "evaluated": len(lf_ok),
            "errors": sum(1 for r in rows if r["langfuse"] and "error" in r["langfuse"]),
            "overall_score": _mean([l["overall_score"] for l in lf_ok]),
            "pass_rate": _mean([1.0 if l["passed"] else 0.0 for l in lf_ok]),
        },
        "agreement": agreement_counts,
        "correlation": {
            "langfuse_overall_vs_adk_response_match": _pearson(lf_scores, rouge),
            "langfuse_overall_vs_adk_rubric_quality": _pearson(*_paired(scored, "rubric_based_final_response_quality_v1")),
            "n": len(scored),
        },
    }
    return {"rows": rows, "aggregate": aggregate}


@asynccontextmanager
async def _model_scope(model: Optional[str]):
    """Apply a model override for the ADK leg under the shared experiment lock; always restore."""
    from app.agents.adk_fleet import refresh_adk_fleet_models
    from app.core.llm_bridge import restore_model_state, set_active_model, snapshot_model_state
    from app.services.dataset_sync_service import _experiment_lock

    async with _experiment_lock:
        state = snapshot_model_state()
        try:
            if model:
                refresh_adk_fleet_models(set_active_model(model))
            yield
        finally:
            restore_model_state(state)
            refresh_adk_fleet_models(None)


def _attach_adk_scores_to_langfuse(dataset_run_id: Optional[str], aggregate: Dict[str, Any]) -> Dict[str, Any]:
    """Record the ADK aggregates on the Langfuse experiment run, so both evaluators show up side by side there."""
    from app.observability import langfuse_client

    client = langfuse_client.get_langfuse()
    if client is None or not dataset_run_id:
        return {"attached": False, "reason": "Langfuse disabled or the run has no dataset_run_id"}
    adk = aggregate["adk"]
    wanted = {f"adk_{name}": value for name, value in adk["metrics"].items()}
    wanted["adk_pass_rate"] = adk["pass_rate"]
    attached = []
    for name, value in wanted.items():
        if value is None:
            continue
        try:
            client.create_score(
                name=name, value=float(value), dataset_run_id=dataset_run_id, data_type="NUMERIC",
                score_id=f"{dataset_run_id}-{name}",
                comment="Google ADK evaluator, same cases, agent fleet only (no guardrail layer)",
            )
            attached.append(name)
        except Exception as exc:
            logger.warning("Could not attach %s to Langfuse run %s: %s", name, dataset_run_id, exc)
    client.flush()
    return {"attached": bool(attached), "scores": attached, "dataset_run_id": dataset_run_id}


async def run_adk_langfuse_comparison(
    test_ids: Optional[List[str]] = None,
    *,
    model: Optional[str] = None,
    judge: Optional[str] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Run the same golden cases through ADK's evaluators and the Langfuse pipeline, then compare."""
    from app.services.dataset_sync_service import langfuse_dataset_service

    started = time.time()
    # An LLM judge by default; pass judge="heuristic" to force the weaker keyword rules.
    if judge is None:
        judge = resolve_default_judge()
    elif judge.lower() == HEURISTIC_JUDGE:
        judge = None
    on_throwaway_db = "sqlite" in settings.DATABASE_URL
    cases = adk_cases(test_ids, include_mutating=on_throwaway_db)
    if limit:
        cases = cases[:limit]
    requested = {c.test_id for c in adk_cases(test_ids)} if test_ids else {tc.test_id for tc in GOLDEN_BENCHMARK_25}
    skipped = sorted(requested - {c.test_id for c in cases}) if not limit else []
    if not cases:
        raise ValueError("No runnable cases: every selected case writes data and the database is not a throwaway SQLite file.")
    ids = [c.test_id for c in cases]

    adk_judge = judge or build_eval_config()["criteria"]["final_response_match_v2"]["judge_model_options"]["judge_model"]
    eval_set = to_eval_set(eval_set_id="adk_compare", test_ids=ids)
    async with _model_scope(model):
        adk_results = await run_adk_evaluation(eval_set, build_eval_config(adk_judge), test_ids=ids)

    langfuse_result = await langfuse_dataset_service.run_golden_benchmark_experiment(
        experiment_run_name=f"adk-compare-{(model or 'default').split('/')[-1]}-{int(started)}",
        model_name=model,
        test_ids=ids,
        judge_model=judge,
    )

    report = build_report(cases, adk_results, langfuse_result.get("results", []))
    scores = _attach_adk_scores_to_langfuse(langfuse_result.get("dataset_run_id"), report["aggregate"])

    warnings = []
    if judge is None:
        warnings.append(
            "Langfuse scores come from the keyword-heuristic judge (no LLM judge was available or requested); "
            "they only check for expected words. Set an OpenAI/Groq key or pass a judge model for a meaningful comparison."
        )
    if settings.MOCK_LLM_ENABLED:
        warnings.append("MOCK_LLM_ENABLED=true: both legs ran on the mock provider; scores say nothing about a real model.")
    if skipped:
        warnings.append(
            f"Skipped {len(skipped)} case(s) whose trajectories write data (apply leave / log hours / Zoho sync) "
            "because the database is not a throwaway SQLite file. Run scripts/run_adk_comparison.py for those."
        )
    return {
        "status": "complete",
        "model": langfuse_result.get("model") or model,
        "judge": langfuse_result.get("judge") or "heuristic",
        "adk_judge": adk_judge,
        "mock_mode": bool(settings.MOCK_LLM_ENABLED),
        "warnings": warnings,
        "skipped_cases": skipped,
        "langfuse_run": {"run_name": langfuse_result.get("run_name"), "url": langfuse_result.get("dataset_run_url")},
        "adk_scores_attached_to_langfuse_run": scores,
        "metric_guide": METRIC_GUIDE,
        **report,
        "duration_sec": round(time.time() - started, 1),
    }
