"""ADK leg: optimise the root prompt with ADK's `GEPARootAgentPromptOptimizer`, executing the REAL agents.

ADK wraps GEPA around an `Agent`: every metric call clones the root agent with the candidate prompt, runs the
case through ADK's evaluation service (real model calls, real sub-agents and tools on the isolated database) and
returns a score plus the trajectory the reflection model reads. `RouteSampler` is that bridge. It scores with the
same formula as the DSPy leg (`common.score_run`) but from what the agents actually did.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from app.evaluations.adk_expectations import to_eval_set
from app.evaluations.adk_support import run_adk_evaluation
from app.optimization.common import OptCase, average, route_of, score_run
from app.optimization.metric import eval_config_for
from app.optimization.runtime import to_adk_instruction

logger = logging.getLogger(__name__)


@dataclass
class AdkCandidate:
    prompt: str
    val_score: Optional[float]


@dataclass
class AdkOptResult:
    seed_prompt: str
    best_prompt: str
    seed_val_score: Optional[float]
    best_val_score: Optional[float]
    metric_calls: int
    candidates: List[AdkCandidate] = field(default_factory=list)


def _make_sampler_class() -> type:
    """Built lazily so importing this module does not require the evaluation extras."""
    from google.adk.optimization.data_types import UnstructuredSamplingResult
    from google.adk.optimization.sampler import Sampler

    class RouteSampler(Sampler[UnstructuredSamplingResult]):
        def __init__(self, cases: Sequence[OptCase], train_ids: Sequence[str], val_ids: Sequence[str]) -> None:
            self.cases = {c.test_id: c for c in cases}
            self._train_ids, self._val_ids = list(train_ids), list(val_ids)
            self._eval_set = to_eval_set(eval_set_id="adk_gepa", test_ids=list(self.cases), with_rubrics=False)
            self._eval_config = eval_config_for("fast", None)   # no judge calls: the score comes from route + reply rules
            self.metric_calls = 0

        def get_train_example_ids(self) -> List[str]:
            return list(self._train_ids)

        def get_validation_example_ids(self) -> List[str]:
            return list(self._val_ids)

        async def sample_and_score(self, candidate: Any, example_set: str = "validation",
                                   batch: Optional[List[str]] = None, capture_full_eval_data: bool = False) -> Any:
            ids = list(batch or (self._train_ids if example_set == "train" else self._val_ids))
            agent = candidate.clone(update={"instruction": to_adk_instruction(candidate.instruction)})
            results = await run_adk_evaluation(self._eval_set, self._eval_config, root_agent=agent, test_ids=ids)
            by_id = {r.test_id: r for r in results}
            scores: Dict[str, float] = {}
            data: Dict[str, Dict[str, Any]] = {}
            for case_id in ids:
                case, result = self.cases[case_id], by_id.get(case_id)
                self.metric_calls += 1
                if result is None or (result.error and not result.actual_tool_use and not result.response):
                    # Provider failure: neutral score, never "wrong routing" (the optimiser would learn from noise).
                    scores[case_id] = 0.0
                    data[case_id] = {"feedback": f"Case could not run: {getattr(result, 'error', 'no result')}"}
                    continue
                route = route_of(result.actual_tool_use)
                score, feedback = score_run(case, route, result.response, reply_measured=True)
                scores[case_id] = score
                data[case_id] = {
                    "question": case.query, "expected_route": case.expected_route, "actual_route": route,
                    "tools_called": [c["tool_name"] for c in result.actual_tool_use], "reply": (result.response or "")[:400],
                    "feedback": feedback,
                }
            return UnstructuredSamplingResult(scores=scores, data=data if capture_full_eval_data else None)

    return RouteSampler


def make_sampler(cases: Sequence[OptCase], train: Sequence[OptCase], val: Sequence[OptCase]) -> Any:
    return _make_sampler_class()(cases, [c.test_id for c in train], [c.test_id for c in val])


async def evaluate_prompt_on_adk(sampler: Any, root_agent: Any, prompt: str, cases: Sequence[OptCase]) -> Dict[str, Any]:
    """Real-agent score of a prompt on cases (one metric call per case): average plus what each case did."""
    agent = root_agent.clone(update={"instruction": prompt})
    result = await sampler.sample_and_score(agent, batch=[c.test_id for c in cases], capture_full_eval_data=True)
    per_case = {
        case_id: {"score": score, "expected": (result.data or {}).get(case_id, {}).get("expected_route"),
                  "actual": (result.data or {}).get(case_id, {}).get("actual_route")}
        for case_id, score in result.scores.items()
    }
    return {"score": average(list(result.scores.values())), "cases": per_case}


async def run_adk_gepa(
    seed_prompt: str,
    root_agent: Any,
    cases: Sequence[OptCase],
    train: Sequence[OptCase],
    val: Sequence[OptCase],
    *,
    reflection_model: str,
    max_metric_calls: int,
    minibatch_size: int = 3,
) -> AdkOptResult:
    """Run ADK's GEPA optimiser from `seed_prompt`; `max_metric_calls` counts real agent runs."""
    from google.adk.optimization.gepa_root_agent_prompt_optimizer import (
        GEPARootAgentPromptOptimizer, GEPARootAgentPromptOptimizerConfig,
    )
    from google.genai import types as genai_types

    from app.core.llm_bridge import export_provider_keys_to_env

    export_provider_keys_to_env()
    sampler = make_sampler(cases, train, val)
    initial = root_agent.clone(update={"instruction": seed_prompt})
    config = GEPARootAgentPromptOptimizerConfig(
        optimizer_model=reflection_model,
        # ADK's default asks for Gemini "thinking" output; plain generation works with every LiteLLM provider.
        model_configuration=genai_types.GenerateContentConfig(temperature=1.0),
        max_metric_calls=max_metric_calls,
        reflection_minibatch_size=minibatch_size,
    )
    result = await GEPARootAgentPromptOptimizer(config).optimize(initial, sampler)

    raw = result.gepa_result or {}
    prompts = [c.get("agent_prompt") if isinstance(c, dict) else str(c) for c in raw.get("candidates", [])]
    scores = [float(s) for s in raw.get("val_aggregate_scores", [])]
    candidates = [AdkCandidate(p, round(scores[i], 4) if i < len(scores) else None) for i, p in enumerate(prompts)]
    best_index = raw.get("best_idx")
    if best_index is None and scores:
        best_index = max(range(len(scores)), key=lambda i: scores[i])
    best = candidates[best_index] if best_index is not None and best_index < len(candidates) else AdkCandidate(seed_prompt, None)
    return AdkOptResult(
        seed_prompt=seed_prompt,
        best_prompt=best.prompt,
        seed_val_score=candidates[0].val_score if candidates else None,
        best_val_score=best.val_score,
        metric_calls=sampler.metric_calls,
        candidates=candidates,
    )
