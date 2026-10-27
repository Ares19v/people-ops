"""What both optimisation legs share: the cases, the split, the seed prompts and the score.

The root orchestrator prompt controls two things: which specialist the question is handed to (or none, for
refusals and questions it answers itself) and what it says when it answers directly. It does not control the
specialists' tool arguments. So both legs score the same two things, with the same formula:

    score = 0.7 * route + 0.3 * reply

* route - the first `transfer_to_agent` target equals the expected specialist (no hand-off expected: none made).
* reply - the golden case's keyword and forbidden-term rules on the answer (see `reply_rules`).

The DSPy leg predicts the route and mocks everything after the hand-off (the specialist's answer counts as
correct); the ADK leg runs the real agents and reads the real route and answer.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROUTE_WEIGHT = 0.7
REPLY_WEIGHT = 0.3

# What the root agent knows about its specialists (taken from the sub-agents' ADK descriptions).
SPECIALISTS: Dict[str, str] = {
    "leave_agent": "Leave balances (CL, EL, SL, LWP), leave eligibility and submitting leave requests.",
    "timesheet_agent": "Timesheet summaries, logging project hours, daily/weekly overtime boundaries.",
    "health_agent": "Occupational health guidelines, medical certificate requirements, health leave triage.",
    "policy_agent": "Indian labour law (Maharashtra Shops & Establishments Act 2017 and others) and HR handbook policies.",
    "zoho_agent": "Zoho People HRMS integration: synchronised attendance and leave records.",
}
NO_HANDOFF = "none"

# Deliberately poor root prompts to optimise. `vague` says almost nothing; `misleading` actively discourages routing.
SEED_PROMPTS: Dict[str, str] = {
    "vague": "You are an HR bot. Answer employee questions. Keep it short.",
    "misleading": (
        "You are an HR helper. Answer every question yourself in one or two sentences. "
        "Do not pass questions to other agents; they are slow."
    ),
}


@dataclass
class OptCase:
    test_id: str
    query: str
    expected_route: Optional[str]          # specialist name, or None when no hand-off is expected
    must_contain: List[str] = field(default_factory=list)
    forbidden: List[str] = field(default_factory=list)
    reference: str = ""


def load_cases(*, pool: str = "golden") -> List[OptCase]:
    """Non-mutating golden cases (mutating ones change the database between candidates and would skew scores)."""
    from app.evaluations.adk_expectations import EXPECTATIONS, adk_cases
    from app.evaluations.golden_dataset_25 import GOLDEN_BENCHMARK_25

    gold = {g.test_id: g for g in GOLDEN_BENCHMARK_25}
    cases: List[OptCase] = []
    for case in adk_cases(include_mutating=False):
        if pool == "deterministic" and not EXPECTATIONS[case.test_id].deterministic:
            continue
        route = next(
            (c["tool_input"].get("agent_name") for c in case.expected_tool_use if c["tool_name"] == "transfer_to_agent"), None
        )
        g = gold[case.test_id]
        cases.append(OptCase(case.test_id, case.query, route, list(g.must_contain_keywords), list(g.forbidden_terms), case.reference))
    return cases


def split_cases(cases: Sequence[OptCase], *, seed: int = 7, train: float = 0.35, val: float = 0.35) -> Tuple[List[OptCase], List[OptCase], List[OptCase]]:
    """Train (reflection), validation (candidate selection) and test (final comparison), stratified by expected route."""
    rng = random.Random(seed)
    groups: Dict[Optional[str], List[OptCase]] = {}
    for case in cases:
        groups.setdefault(case.expected_route, []).append(case)
    tr: List[OptCase] = []
    va: List[OptCase] = []
    te: List[OptCase] = []
    for _, members in sorted(groups.items(), key=lambda kv: str(kv[0])):
        members = sorted(members, key=lambda c: c.test_id)
        rng.shuffle(members)
        n = len(members)
        n_tr = max(1, round(n * train)) if n > 2 else 1
        n_va = max(1, round(n * val)) if n > 2 else (1 if n == 2 else 0)
        tr += members[:n_tr]
        va += members[n_tr:n_tr + n_va]
        te += members[n_tr + n_va:]
    if not te:  # tiny pools: reuse validation cases so the final comparison is never empty
        te = list(va)
    return tr, va, te


def route_of(tool_calls: Sequence[Dict[str, Any]]) -> Optional[str]:
    """The first specialist the agent handed the question to, or None."""
    for call in tool_calls:
        if call.get("tool_name") == "transfer_to_agent":
            return (call.get("tool_input") or {}).get("agent_name")
    return None


def reply_rules(case: OptCase, reply: Optional[str]) -> Tuple[float, List[str]]:
    """0..1 plus the reasons it is below 1. Forbidden text zeroes it; keywords give partial credit."""
    text = (reply or "").lower()
    issues: List[str] = []
    if not text.strip():
        return 0.0, ["empty reply"]
    leaked = [t for t in case.forbidden if t.lower() in text]
    if leaked:
        return 0.0, [f"reply contains forbidden text {leaked}"]
    if not case.must_contain:
        return 1.0, issues
    hits = [k for k in case.must_contain if k.lower() in text]
    needed = min(len(case.must_contain), 3)
    score = min(1.0, len(hits) / needed)
    if score < 1.0:
        issues.append(f"reply mentions {len(hits)} of the expected terms {case.must_contain}")
    return score, issues


def score_run(case: OptCase, route: Optional[str], reply: Optional[str], *, reply_measured: bool = True) -> Tuple[float, str]:
    """(score, feedback) for one case. `reply_measured=False` (mocked specialist) counts the reply as correct
    whenever a hand-off was expected; direct answers are always judged."""
    route_ok = (route or None) == (case.expected_route or None)
    if reply_measured or case.expected_route is None:
        reply_score, issues = reply_rules(case, reply)
    else:
        reply_score, issues = 1.0, []
    score = round(ROUTE_WEIGHT * (1.0 if route_ok else 0.0) + REPLY_WEIGHT * reply_score, 4)

    expected = case.expected_route or "no hand-off (answer or refuse directly)"
    actual = route or "no hand-off"
    lines = [f"Question: {case.query}", f"Expected: {expected}. Actual: {actual}. Score {score:.2f} of 1.0."]
    if not route_ok:
        if case.expected_route:
            lines.append(f"Wrong routing: this question belongs to {case.expected_route} ({SPECIALISTS.get(case.expected_route, '')}).")
        else:
            lines.append("This question must NOT be handed to a specialist: it is a guardrail case (prompt injection, off-topic, "
                         "or something the orchestrator answers itself) and needs a direct, safe reply.")
    lines += [f"Reply problem: {i}" for i in issues]
    if reply:
        lines.append(f"Reply was: {reply[:300]}")
    return score, "\n".join(lines)


def average(values: Sequence[Optional[float]]) -> Optional[float]:
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 4) if present else None
