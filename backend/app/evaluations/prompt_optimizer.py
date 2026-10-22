"""Reflective prompt optimisation for the grid-testing harness (GEPA-style, single candidate).

Given the best prompt from a grid run and the items it still fails, an optimiser LLM is asked to
rewrite the prompt using the failures and the judge's feedback; each candidate is re-scored with
the same judge on the same items and kept only if it improves. The loop is bounded by the number of
reflection rounds (`budget`) and by `max_metric_calls` (one call = one item evaluated).

This is deliberately simpler than the full GEPA algorithm (no Pareto front, no merging of
candidates): it evolves one prompt greedily. The result is only ever published under an explicit
non-live label so a human reviews it before promotion.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

BUDGET_ROUNDS: Dict[str, int] = {"light": 2, "medium": 4, "heavy": 8}
PROTECTED_LABELS = {"live", "production", "latest"}
_PLACEHOLDER = re.compile(r"\{\{\s*[\w.]+\s*\}\}")


@dataclass
class EvalOutcome:
    """Result of scoring one prompt on the optimisation items."""
    avg_score: float
    failures: List[Dict[str, Any]]  # items below threshold: prompt, response, score, metrics, feedback
    metric_calls: int               # items evaluated to produce this outcome


@dataclass
class OptimizationResult:
    seed_score: float
    best_score: float
    best_prompt: str
    improved: bool
    stopped_reason: str  # threshold_met | rounds_exhausted | metric_call_budget | no_candidate
    metric_calls: int
    rounds: List[Dict[str, Any]] = field(default_factory=list)


def candidate_is_valid(seed: str, candidate: Optional[str]) -> bool:
    """A rewrite must be non-trivial, keep every template placeholder, and not balloon in size."""
    if not candidate or not candidate.strip():
        return False
    candidate = candidate.strip()
    if candidate == seed.strip():
        return False
    if len(candidate) > max(2 * len(seed), 4000):
        return False
    return set(_PLACEHOLDER.findall(seed)) <= set(_PLACEHOLDER.findall(candidate))


class ReflectivePromptOptimizer:
    def __init__(
        self,
        evaluate: Callable[[str], Awaitable[EvalOutcome]],
        reflect: Callable[[str, List[Dict[str, Any]]], Awaitable[Optional[str]]],
        *,
        threshold: float = 0.8,
        budget: str = "light",
        max_metric_calls: int = 10,
    ) -> None:
        self.evaluate = evaluate
        self.reflect = reflect
        self.threshold = threshold
        self.max_rounds = BUDGET_ROUNDS.get(budget, BUDGET_ROUNDS["light"])
        self.max_metric_calls = max(1, int(max_metric_calls))

    async def optimize(self, seed_prompt: str, seed_outcome: EvalOutcome) -> OptimizationResult:
        best_prompt, best = seed_prompt, seed_outcome
        calls = 0
        rounds: List[Dict[str, Any]] = []
        stopped = "rounds_exhausted"

        if best.avg_score >= self.threshold:
            return OptimizationResult(best.avg_score, best.avg_score, best_prompt, False, "threshold_met", 0, rounds)

        for number in range(1, self.max_rounds + 1):
            if calls + max(1, seed_outcome.metric_calls) > self.max_metric_calls:
                stopped = "metric_call_budget"
                break

            try:
                candidate = await self.reflect(best_prompt, best.failures)
            except Exception as exc:
                logger.warning("Prompt reflection failed in round %s: %s", number, exc)
                candidate = None
            if not candidate_is_valid(best_prompt, candidate):
                rounds.append({"round": number, "accepted": False, "reason": "no usable rewrite"})
                stopped = "no_candidate"
                break

            outcome = await self.evaluate(candidate.strip())
            calls += outcome.metric_calls
            accepted = outcome.avg_score > best.avg_score
            rounds.append({
                "round": number,
                "candidate_score": round(outcome.avg_score, 3),
                "previous_best": round(best.avg_score, 3),
                "accepted": accepted,
                "metric_calls": outcome.metric_calls,
            })
            if accepted:
                best_prompt, best = candidate.strip(), outcome
            if best.avg_score >= self.threshold:
                stopped = "threshold_met"
                break

        return OptimizationResult(
            seed_score=seed_outcome.avg_score,
            best_score=best.avg_score,
            best_prompt=best_prompt,
            improved=best.avg_score > seed_outcome.avg_score,
            stopped_reason=stopped,
            metric_calls=calls,
            rounds=rounds,
        )
