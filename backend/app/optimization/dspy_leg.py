"""DSPy leg: optimise the root prompt with `dspy.GEPA` against a MOCKED agent.

DSPy wraps GEPA around `dspy.Module` programs, and a program is just LM calls: there is no agent runtime in the
loop. The mock is therefore the root orchestrator reduced to its one decision (hand off to which specialist, or
answer directly), with the instruction of that single predictor being the root prompt. Nothing after the
hand-off is executed; the specialist's answer is assumed correct (`score_run(reply_measured=False)`). That makes a
metric call one cheap LLM call, so this leg can afford many of them.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from app.optimization.common import NO_HANDOFF, SPECIALISTS, OptCase, average, score_run

logger = logging.getLogger(__name__)

PREDICTOR_NAME = "decide"
_EMPLOYEE_HEADER = "[Active Employee: Aarav Sharma (ID: EMP-004) - Address as Aarav, NEVER call by ID code]"


@dataclass
class DspyCandidate:
    prompt: str
    val_score: Optional[float]


@dataclass
class DspyResult:
    seed_prompt: str
    best_prompt: str
    seed_val_score: Optional[float]
    best_val_score: Optional[float]
    metric_calls: int
    candidates: List[DspyCandidate] = field(default_factory=list)
    mock_scores: Dict[str, Optional[float]] = field(default_factory=dict)   # split -> mocked score of the best prompt


def _catalogue() -> str:
    return "\n".join(f"- {name}: {desc}" for name, desc in SPECIALISTS.items())


def normalise_route(raw: Any) -> Optional[str]:
    """The specialist named in the model's `handoff` field, or None for 'no hand-off'."""
    text = str(raw or "").strip().lower().replace("`", "").replace('"', "").replace("'", "")
    for name in SPECIALISTS:
        if name in text:
            return name
    return None


def build_examples(cases: Sequence[OptCase]) -> List[Any]:
    import dspy

    return [
        dspy.Example(
            case_id=c.test_id, employee_header=_EMPLOYEE_HEADER, question=c.query, specialists=_catalogue(), case=c,
        ).with_inputs("employee_header", "question", "specialists")
        for c in cases
    ]


def build_program(instructions: str) -> Any:
    """One predictor whose instruction is the root prompt: the mocked root orchestrator."""
    import dspy

    class RootDecision(dspy.Signature):
        employee_header: str = dspy.InputField(desc="Who is asking")
        question: str = dspy.InputField(desc="The employee's message")
        specialists: str = dspy.InputField(desc="The specialist agents you can hand the question to")
        handoff: str = dspy.OutputField(desc=f"Exactly one of: {', '.join(SPECIALISTS)}, {NO_HANDOFF}")
        reply: str = dspy.OutputField(desc="Your direct reply when handoff is none; leave empty when you hand off")

    class MockedRootAgent(dspy.Module):
        def __init__(self) -> None:
            super().__init__()
            setattr(self, PREDICTOR_NAME, dspy.Predict(RootDecision.with_instructions(instructions)))

        def forward(self, employee_header: str, question: str, specialists: str, **_: Any):
            return getattr(self, PREDICTOR_NAME)(employee_header=employee_header, question=question, specialists=specialists)

    return MockedRootAgent()


def metric(gold: Any, pred: Any, trace: Any = None, pred_name: Optional[str] = None, pred_trace: Any = None) -> Any:
    """GEPA metric: a score plus the feedback text its reflection model learns from."""
    import dspy

    case: OptCase = gold.case
    score, feedback = score_run(case, normalise_route(getattr(pred, "handoff", None)), getattr(pred, "reply", ""), reply_measured=False)
    return dspy.Prediction(score=score, feedback=feedback)


def _instructions_of(program: Any) -> str:
    return getattr(program, PREDICTOR_NAME).signature.instructions


def evaluate_prompt(prompt: str, cases: Sequence[OptCase]) -> Optional[float]:
    """Mocked score of a prompt on cases (one LM call per case), using whichever LM is configured in dspy."""
    program = build_program(prompt)
    scores: List[Optional[float]] = []
    for example in build_examples(cases):
        try:
            result = metric(example, program(**example.inputs()))
            scores.append(float(result.score))
        except Exception as exc:  # a provider error is not a wrong answer
            logger.warning("DSPy mock evaluation of %s failed: %s", example.case_id, exc)
            scores.append(None)
    return average(scores)


def run_dspy_gepa(
    seed_prompt: str,
    train: Sequence[OptCase],
    val: Sequence[OptCase],
    test: Sequence[OptCase] = (),
    *,
    task_model: str,
    reflection_model: str,
    max_metric_calls: int,
    minibatch_size: int = 3,
    num_threads: int = 4,
) -> DspyResult:
    """Run `dspy.GEPA` from `seed_prompt` and return the best prompt it found.

    `max_metric_calls` counts example evaluations (each is one LM call here), exactly as in the ADK leg.
    """
    import dspy

    from app.core.llm_bridge import export_provider_keys_to_env

    export_provider_keys_to_env()
    task_lm = dspy.LM(task_model, temperature=0.0, max_tokens=700, cache=False)
    reflection_lm = dspy.LM(reflection_model, temperature=1.0, max_tokens=4000, cache=False)
    dspy.configure(lm=task_lm)

    student = build_program(seed_prompt)
    seed_val = evaluate_prompt(seed_prompt, val)
    optimizer = dspy.GEPA(
        metric=metric,
        reflection_lm=reflection_lm,
        max_metric_calls=max_metric_calls,
        reflection_minibatch_size=minibatch_size,
        num_threads=num_threads,
        track_stats=True,
        seed=7,
    )
    optimized = optimizer.compile(student, trainset=build_examples(train), valset=build_examples(val))
    best_prompt = _instructions_of(optimized)

    details = getattr(optimized, "detailed_results", None)
    candidates: List[DspyCandidate] = []
    calls = 0
    if details is not None:
        scores = list(getattr(details, "val_aggregate_scores", []) or [])
        for index, program in enumerate(getattr(details, "candidates", []) or []):
            candidates.append(DspyCandidate(_instructions_of(program), round(float(scores[index]), 4) if index < len(scores) else None))
        calls = int(getattr(details, "total_metric_calls", 0) or 0)
        best_index = getattr(details, "best_idx", None)
        best_val = candidates[best_index].val_score if best_index is not None and best_index < len(candidates) else None
    else:
        best_val = None
    if best_val is None:
        best_val = evaluate_prompt(best_prompt, val)

    return DspyResult(
        seed_prompt=seed_prompt,
        best_prompt=best_prompt,
        seed_val_score=seed_val,
        best_val_score=best_val,
        metric_calls=calls,
        candidates=candidates,
        mock_scores={"val": best_val, "test": evaluate_prompt(best_prompt, test) if test else None},
    )
