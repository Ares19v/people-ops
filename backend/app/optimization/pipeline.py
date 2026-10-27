"""Optimise a poor root prompt two ways and compare the results on the real agents.

    seed ──► DSPy GEPA (mocked agent, many cheap metric calls) ──► best DSPy prompt
                                                                         │ becomes the ADK seed
                                                                         ▼
    seed ─────────────────────────────────────────────────────► ADK GEPA (real agents, few costly metric calls)

Both legs run on the same GEPA engine with the same cases, split and score, so their numbers mean the same thing.
The DSPy leg explores cheaply; the ADK leg starts from its winner and corrects whatever the mock got wrong
(the mock cannot see a real hand-off or a real answer). Finally the seed and every winner are scored on the
held-out test cases with the real agents, which is the only comparison that counts.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from app.optimization.common import SEED_PROMPTS, average, load_cases, split_cases

logger = logging.getLogger(__name__)


async def run_optimization(
    *,
    root_agent: Any,
    seed_prompt: str,
    mode: str = "both",                       # dspy | adk | both
    pool: str = "golden",
    task_model: str = "openai/gpt-4o-mini",
    reflection_model: str = "openai/gpt-4o-mini",
    dspy_calls: int = 60,
    adk_calls: int = 40,
    minibatch_size: int = 3,
    split_seed: int = 7,
) -> Dict[str, Any]:
    from app.agents.adk_fleet import refresh_adk_fleet_models, set_root_instruction_override
    from app.core.llm_bridge import restore_model_state, set_active_model, snapshot_model_state
    from app.optimization.adk_leg import evaluate_prompt_on_adk, make_sampler, run_adk_gepa
    from app.optimization.dspy_leg import run_dspy_gepa

    if mode not in ("dspy", "adk", "both"):
        raise ValueError("mode must be dspy, adk or both")
    started = time.time()
    cases = load_cases(pool=pool)
    train, val, test = split_cases(cases, seed=split_seed)
    report: Dict[str, Any] = {
        "mode": mode, "pool": pool, "task_model": task_model, "reflection_model": reflection_model,
        "budget": {"dspy_metric_calls": dspy_calls if mode != "adk" else 0, "adk_metric_calls": adk_calls if mode != "dspy" else 0},
        "split": {"train": [c.test_id for c in train], "val": [c.test_id for c in val], "test": [c.test_id for c in test]},
        "seed_prompt": seed_prompt, "legs": {},
    }

    state = snapshot_model_state()
    try:
        refresh_adk_fleet_models(set_active_model(task_model))
        sampler = make_sampler(cases, train, val)
        candidates: Dict[str, str] = {"seed": seed_prompt}
        adk_seed = seed_prompt

        if mode in ("dspy", "both"):
            logger.info("DSPy leg: %s metric calls on the mocked agent", dspy_calls)
            # Own thread: DSPy drives its own threads and must not start inside this event loop.
            dspy_result = await asyncio.to_thread(
                run_dspy_gepa, seed_prompt, train, val, test, task_model=task_model, reflection_model=reflection_model,
                max_metric_calls=dspy_calls, minibatch_size=minibatch_size,
            )
            report["legs"]["dspy"] = {
                "engine": "dspy.GEPA", "agent_execution": "mocked", "metric_calls": dspy_result.metric_calls,
                "mock_val_seed": dspy_result.seed_val_score, "mock_val_best": dspy_result.best_val_score,
                "mock_test_best": dspy_result.mock_scores.get("test"), "candidates_tried": len(dspy_result.candidates),
                "improved": (dspy_result.best_val_score or 0) > (dspy_result.seed_val_score or 0), "best_prompt": dspy_result.best_prompt,
            }
            candidates["dspy"] = dspy_result.best_prompt
            if report["legs"]["dspy"]["improved"]:
                adk_seed = dspy_result.best_prompt

        if mode in ("adk", "both"):
            logger.info("ADK leg: %s metric calls on the real agents, seeded from %s", adk_calls, "the DSPy winner" if adk_seed != seed_prompt else "the seed")
            adk_result = await run_adk_gepa(
                adk_seed, root_agent, cases, train, val, reflection_model=reflection_model,
                max_metric_calls=adk_calls, minibatch_size=minibatch_size,
            )
            report["legs"]["adk"] = {
                "engine": "google.adk GEPARootAgentPromptOptimizer", "agent_execution": "real",
                "seeded_from": "dspy" if adk_seed != seed_prompt else "seed", "metric_calls": adk_result.metric_calls,
                "val_seed": adk_result.seed_val_score, "val_best": adk_result.best_val_score,
                "candidates_tried": len(adk_result.candidates),
                "improved": (adk_result.best_val_score or 0) > (adk_result.seed_val_score or 0), "best_prompt": adk_result.best_prompt,
            }
            candidates["adk"] = adk_result.best_prompt

        # Final comparison: every candidate, real agents, same cases.
        comparison: Dict[str, Dict[str, Optional[float]]] = {}
        per_case: Dict[str, Dict[str, Any]] = {}
        for name, prompt in candidates.items():
            full = await evaluate_prompt_on_adk(sampler, root_agent, prompt, cases)   # one pass; split scores derive from it
            by_id = {cid: v["score"] for cid, v in full["cases"].items()}
            comparison[name] = {
                "val": average([by_id.get(c.test_id) for c in val]),
                "test": average([by_id.get(c.test_id) for c in test]),
                "all": full["score"],
            }
            per_case[name] = full["cases"]
        report["comparison"] = comparison
        report["per_case"] = per_case
        ranked = sorted(comparison, key=lambda n: (comparison[n]["val"] or 0, comparison[n]["test"] or 0), reverse=True)
        winner = ranked[0]
        report["winner"] = {"name": winner, "prompt": candidates[winner], **comparison[winner],
                            "gain_on_test": round((comparison[winner]["test"] or 0) - (comparison["seed"]["test"] or 0), 4)}
        report["candidates"] = candidates
    finally:
        restore_model_state(state)
        set_root_instruction_override(None)
        refresh_adk_fleet_models(None)

    report["duration_sec"] = round(time.time() - started, 1)
    return report


def to_markdown(report: Dict[str, Any]) -> str:
    cmp_, win = report["comparison"], report["winner"]
    fmt = lambda v: "n/a" if v is None else f"{v:.3f}"  # noqa: E731
    lines = [
        f"# Prompt optimisation ({report['mode']})", "",
        f"Task model `{report['task_model']}`, reflection model `{report['reflection_model']}`, pool `{report['pool']}`, "
        f"{len(report['split']['train'])} train / {len(report['split']['val'])} val / {len(report['split']['test'])} test cases, "
        f"{report['duration_sec']}s.", "",
        "## Scores on the real agents (same cases for every prompt)", "",
        "| prompt | val | test (held out) | all cases |", "|---|---|---|---|",
    ]
    for name, row in cmp_.items():
        lines.append(f"| {name}{' (winner)' if name == win['name'] else ''} | {fmt(row['val'])} | {fmt(row['test'])} | {fmt(row['all'])} |")
    lines += ["", f"Winner **{win['name']}**: {win['gain_on_test']:+.3f} on held-out test cases versus the seed.", ""]
    seed_cases, win_cases = report["per_case"]["seed"], report["per_case"][win["name"]]
    split_of = {cid: s for s, ids in report["split"].items() for cid in ids}
    changed = [(cid, seed_cases[cid], win_cases.get(cid)) for cid in seed_cases if win_cases.get(cid) and seed_cases[cid]["score"] != win_cases[cid]["score"]]
    if changed:
        lines += [f"## Cases where {win['name']} differs from the seed", "", "| case | split | expected | seed did | winner did | seed -> winner |", "|---|---|---|---|---|---|"]
        for cid, s, w in changed:
            lines.append(f"| {cid} | {split_of.get(cid, '?')} | {s['expected'] or 'no hand-off'} | {s['actual'] or 'no hand-off'} | "
                         f"{w['actual'] or 'no hand-off'} | {s['score']:.2f} -> {w['score']:.2f} |")
        lines.append("")
    lines += ["## Legs", ""]
    for name, leg in report["legs"].items():
        lines.append(f"- **{name}** ({leg['engine']}, agent execution {leg['agent_execution']}): {leg['metric_calls']} metric calls, "
                     f"{leg['candidates_tried']} candidates, improved on its own validation set: {leg['improved']}.")
    lines += ["", "## Seed prompt", "", "```", report["seed_prompt"], "```", "", f"## Winning prompt ({win['name']})", "", "```", win["prompt"], "```", ""]
    return "\n".join(lines)
