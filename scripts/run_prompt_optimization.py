"""Optimise a poorly written root prompt with GEPA, two ways, and compare on the real agents.

    python scripts/run_prompt_optimization.py                          # DSPy (mocked agent) then ADK (real agents)
    python scripts/run_prompt_optimization.py --mode dspy --dspy-calls 80
    python scripts/run_prompt_optimization.py --mode adk --adk-calls 30 --seed vague
    python scripts/run_prompt_optimization.py --seed @my_prompt.txt --reflection-model groq/openai/gpt-oss-120b

`--dspy-calls` / `--adk-calls` are metric-call budgets (one call = one case evaluated). A DSPy call is one LLM call
with the agent mocked; an ADK call is a full real agent run (about three LLM calls).

When GEPA beats the seed, the winning prompt is pushed to Langfuse as a new version of `peopleops-root-orchestrator`
with the label `gepa-optimized` and the tag "GEPA Optimized". It is never made `live`; promote it yourself after
reviewing it (`--no-publish` skips the push, `--publish-label` changes the label). See docs/05_prompt_optimization.md.
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.optimization.runtime import prepare_adk_runtime  # noqa: E402  (must run before other app imports)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["dspy", "adk", "both"], default="both")
    parser.add_argument("--seed", default="misleading", help="seed prompt: 'misleading', 'vague', @file.txt, or literal text")
    parser.add_argument("--pool", choices=["golden", "deterministic"], default="golden", help="which non-mutating cases to use")
    parser.add_argument("--task-model", default="openai/gpt-4o-mini", help="model the agents / mocked agent run on")
    parser.add_argument("--reflection-model", default="openai/gpt-4o-mini", help="model that proposes prompt rewrites")
    parser.add_argument("--dspy-calls", type=int, default=60, help="metric-call budget of the DSPy leg")
    parser.add_argument("--adk-calls", type=int, default=40, help="metric-call budget of the ADK leg")
    parser.add_argument("--minibatch", type=int, default=3, help="cases per reflection step")
    parser.add_argument("--out", help="report base path without extension (default: reports/optimization_<time>)")
    parser.add_argument("--publish-label", default=None, help="Langfuse label for the optimised prompt (default: gepa-optimized; never live)")
    parser.add_argument("--no-publish", action="store_true", help="do not push the winning prompt to Langfuse")
    parser.add_argument("--prompt-name", default="peopleops-root-orchestrator", help="Langfuse prompt the winner is published to")
    args = parser.parse_args()

    root_agent = prepare_adk_runtime()
    from app.evaluations.prompt_optimizer import GEPA_DEFAULT_LABEL, GEPA_OPTIMIZED_TAG, PROTECTED_LABELS
    from app.optimization.common import SEED_PROMPTS
    from app.optimization.pipeline import run_optimization, to_markdown

    label = args.publish_label or GEPA_DEFAULT_LABEL
    if label in PROTECTED_LABELS:
        print(f"Refusing to publish to protected label '{label}'. Use e.g. '{GEPA_DEFAULT_LABEL}'.")
        return 2
    seed = SEED_PROMPTS.get(args.seed)
    if seed is None:
        seed = Path(args.seed[1:]).read_text(encoding="utf-8") if args.seed.startswith("@") else args.seed

    report = await run_optimization(
        root_agent=root_agent, seed_prompt=seed, mode=args.mode, pool=args.pool, task_model=args.task_model,
        reflection_model=args.reflection_model, dspy_calls=args.dspy_calls, adk_calls=args.adk_calls, minibatch_size=args.minibatch,
    )

    win = report["winner"]
    report["published"] = None
    if args.no_publish:
        print("Publishing skipped (--no-publish).")
    elif win["name"] == "seed":
        print("No GEPA candidate beat the seed prompt, so nothing was pushed to Langfuse.")
    else:
        from app.services.dataset_sync_service import langfuse_dataset_service

        version = langfuse_dataset_service._publish_optimized_prompt(
            args.prompt_name, win["prompt"], label,
            f"GEPA ({report['mode']}, winner {win['name']}): test {report['comparison']['seed']['test']} -> {win['test']} on {report['task_model']}",
        )
        if version is None:
            print("Could not push the optimised prompt to Langfuse (is it connected? see the log above).")
        else:
            report["published"] = {"prompt": args.prompt_name, "version": version, "label": label, "tag": GEPA_OPTIMIZED_TAG}
            print(f"Pushed {args.prompt_name} v{version} to Langfuse: label '{label}', tag '{GEPA_OPTIMIZED_TAG}' (not live).")

    base = Path(args.out) if args.out else BACKEND_DIR / "reports" / f"optimization_{time.strftime('%Y%m%d_%H%M%S')}"
    base.parent.mkdir(parents=True, exist_ok=True)
    base.with_suffix(".json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    base.with_suffix(".md").write_text(to_markdown(report), encoding="utf-8")
    print("\n" + to_markdown(report))
    print(f"report: {base.with_suffix('.md')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
