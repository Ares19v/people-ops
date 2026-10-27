"""One scoring definition shared by the ADK grid and both optimisers.

An ADK case result carries many metrics; GEPA needs one number per example plus text that explains the failure.
`composite` is half "did the agent take the right steps" (tool trajectory, exact match) and half "is the answer
good" (the judged response metrics that are enabled). `feedback` is what the optimiser's reflection model reads.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from app.evaluations.adk_support import AdkCaseResult

TRAJECTORY = "tool_trajectory_avg_score"
QUALITY_METRICS = ("final_response_match_v2", "rubric_based_final_response_quality_v1")

# preset -> ADK criteria that are kept in the eval config
METRIC_PRESETS: Dict[str, List[str]] = {
    "fast": [TRAJECTORY, "response_match_score"],                     # no judge calls at all
    "standard": [TRAJECTORY, "response_match_score", "final_response_match_v2"],
    "full": [
        TRAJECTORY, "response_match_score", "final_response_match_v2", "rubric_based_final_response_quality_v1",
        "rubric_based_tool_use_quality_v1", "hallucinations_v1",
    ],
}


def eval_config_for(preset: str, judge: Optional[str]) -> Dict[str, Any]:
    """ADK criteria restricted to a preset (`fast`, `standard`, `full`)."""
    if preset not in METRIC_PRESETS:
        raise ValueError(f"unknown metric preset '{preset}'; use one of {sorted(METRIC_PRESETS)}")
    from app.evaluations.adk_expectations import build_eval_config

    config = copy.deepcopy(build_eval_config(judge))
    keep = set(METRIC_PRESETS[preset])
    config["criteria"] = {name: value for name, value in config["criteria"].items() if name in keep}
    return config


def composite(result: AdkCaseResult) -> Optional[float]:
    """0..1 score for one case, or None when the case never produced an answer (provider error, not a wrong answer)."""
    if result.error and not result.metrics:
        return None
    trajectory = result.score(TRAJECTORY)
    quality = [s for s in (result.score(name) for name in QUALITY_METRICS) if s is not None]
    parts: List[float] = []
    if trajectory is not None:
        parts.append(float(trajectory))
    if quality:
        parts.append(sum(quality) / len(quality))
    return round(sum(parts) / len(parts), 4) if parts else None


def _fmt_calls(calls: List[Dict[str, Any]]) -> str:
    if not calls:
        return "(no tool calls)"
    return ", ".join(f"{c['tool_name']}({', '.join(f'{k}={v!r}' for k, v in c['tool_input'].items())})" for c in calls)


def feedback(result: AdkCaseResult, query: str) -> str:
    """Plain-text diagnosis of one case for the reflection model."""
    lines = [f"Question: {query}"]
    score = composite(result)
    lines.append(f"Score: {'n/a' if score is None else f'{score:.2f}'} (1.0 is perfect)")
    lines.append(f"Expected steps: {_fmt_calls(result.expected_tool_use)}")
    lines.append(f"Actual steps:   {_fmt_calls(result.actual_tool_use)}")
    if result.response:
        lines.append(f"Final answer: {result.response[:400]}")
    for name, entry in result.metrics.items():
        if entry.get("status") == "FAILED" and entry.get("score") is not None:
            lines.append(f"Failed {name}: {entry['score']:.2f} (needs {entry.get('threshold')})")
            for rubric in entry.get("rubrics", []):
                if rubric.get("score") == 0:
                    lines.append(f"  - rubric '{rubric['rubric_id']}' not met: {(rubric.get('rationale') or '')[:160]}")
    if result.error:
        lines.append(f"Error: {result.error}")
    return "\n".join(lines)
