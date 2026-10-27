"""Run an ADK eval set from the command line with ADK's built-in evaluators.

    python scripts/run_adk_eval.py [--evalset deterministic|golden] [--cases ID1,ID2] [--all]
                                   [--model openai/gpt-4o-mini] [--judge openai/gpt-4o-mini]

Same agent (`hr_root_orchestrator`), same eval-set files the Eval tab in ADK Web uses, run through ADK's own
`LocalEvalService`: tool trajectory, response match, final_response_match_v2, rubric-based response and tool
quality, hallucinations. Tools run against an isolated SQLite database, never the real one.
"""
import argparse
import asyncio
import importlib
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
AGENT_DIR = BACKEND_DIR / "adk_web" / "peopleops"
SMOKE_CASES = ["BENCH-01-LEAVE-BALANCES", "BENCH-11-TIMESHEET-UTILIZATION", "BENCH-22-NEMO-JAILBREAK-DEFENSE"]
sys.path.insert(0, str(BACKEND_DIR))


def _show(result) -> None:
    print(f"\n{result.status or 'ERROR':<10} {result.test_id}")
    if result.error:
        print(f"  error: {result.error}")
    for name, entry in result.metrics.items():
        score = entry["score"]
        shown = "n/a" if score is None else f"{score:.2f}"
        print(f"  {name:<42} {shown:>5}  {entry['status']} (threshold {entry['threshold']})")
        for rubric in entry.get("rubrics", []):
            print(f"      - {rubric['rubric_id']:<34} {rubric['score']}")
    if result.efficiency:
        print("  efficiency: " + ", ".join(f"{k}={v}" for k, v in result.efficiency.items()))


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evalset", choices=["deterministic", "golden"], default="deterministic")
    parser.add_argument("--cases", help="comma-separated eval ids (default: 3 representative cases)")
    parser.add_argument("--all", action="store_true", help="run every eval in the set")
    parser.add_argument("--model", help="agent model, e.g. openai/gpt-4o-mini (default: the backend's provider)")
    parser.add_argument("--judge", help="judge model for the LLM-judged criteria (default: from eval_config.json)")
    parser.add_argument("--json-out", help="write the results to this file")
    args = parser.parse_args()

    if args.model:
        os.environ["ADK_WEB_MODEL"] = args.model
    # Importing the package applies the SQLite isolation, identity shim and model choice.
    sys.path.insert(0, str(BACKEND_DIR / "adk_web"))
    agent = importlib.import_module("peopleops.agent")

    from app.evaluations.adk_expectations import build_eval_config
    from app.evaluations.adk_support import run_adk_evaluation

    eval_set = json.loads((AGENT_DIR / f"peopleops_{args.evalset}.evalset.json").read_text(encoding="utf-8"))
    eval_config = build_eval_config(args.judge) if args.judge else json.loads((AGENT_DIR / "eval_config.json").read_text(encoding="utf-8"))
    selected = None if args.all else ([c.strip() for c in args.cases.split(",")] if args.cases else SMOKE_CASES)

    results = await run_adk_evaluation(eval_set, eval_config, root_agent=agent.root_agent, test_ids=selected)
    for result in results:
        _show(result)
    passed = sum(1 for r in results if r.passed)
    print(f"\n{passed}/{len(results)} evals passed")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps([r.__dict__ for r in results], indent=2, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
