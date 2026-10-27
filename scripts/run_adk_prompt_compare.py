"""Compare any prompt version on any agent against another (ADK has no built-in way to do this).

Each --contestant is key=value pairs (comma separated):
    agent=   root | leave | timesheet | health | policy | zoho           (default root)
    prompt=  Langfuse prompt name                                       (default: the agent's own prompt)
    version= 3  |  label= live | gepa-optimized  |  text= literal text   (one of; default label=live)
    model=   e.g. openai/gpt-4o-mini                                    (default: the backend's current model)
    name=    how to show it in the table                                (optional)

    # root prompt v3 vs the GEPA-optimised version, same agent
    python scripts/run_adk_prompt_compare.py -c agent=root,version=3 -c agent=root,label=gepa-optimized

    # leave-subagent v1 on the leave agent vs v2
    python scripts/run_adk_prompt_compare.py -c agent=leave,version=1 -c agent=leave,version=2

    # different prompts on different agents, each on its own model
    python scripts/run_adk_prompt_compare.py -c agent=policy,version=2,model=openai/gpt-4o-mini \\
                                             -c agent=health,prompt=health-subagent,label=live,model=groq/openai/gpt-oss-120b

    python scripts/run_adk_prompt_compare.py --config compare.json     # {"contestants": [{...}, {...}]}

Every contestant runs the same golden cases on an isolated SQLite database, never the real one. If all contestants
target one specialist agent, only the cases that should reach it are used (override with --items). Nothing has to be
GEPA-optimised: any version, label or text works. `--metrics fast` makes no judge calls.
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


def _csv(value):
    return [v.strip() for v in value.split(",") if v.strip()] if value else []


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-c", "--contestant", action="append", default=[], metavar="SPEC", help="repeatable; at least two")
    parser.add_argument("--config", help='JSON file: {"contestants": [{"agent": "leave", "version": 2}, ...]} (text may contain commas)')
    parser.add_argument("--items", help="comma-separated golden case ids (default: every non-mutating case, or the specialist's own cases)")
    parser.add_argument("--limit", type=int, help="use only the first N cases")
    parser.add_argument("--evalset", choices=["deterministic", "golden"], default="deterministic")
    parser.add_argument("--metrics", choices=["fast", "standard", "full"], default="standard")
    parser.add_argument("--judge", help="judge model for LLM-judged metrics (default: openai/gpt-4o-mini)")
    parser.add_argument("--retry-errors", type=int, default=2, help="re-run errored cases (e.g. rate-limited) this many times after a 65s cooldown")
    parser.add_argument("--out", help="report base path without extension (default: reports/prompt_compare_<time>)")
    args = parser.parse_args()

    root_agent = prepare_adk_runtime()
    from app.optimization.adk_prompt_compare import CompareConfigError, parse_contestant_spec, run_prompt_comparison, to_markdown

    raw = []
    if args.config:
        raw.extend(json.loads(Path(args.config).read_text(encoding="utf-8")).get("contestants", []))
    try:
        raw.extend(parse_contestant_spec(spec) for spec in args.contestant)
        for spec in raw:  # text=@file.txt reads the prompt from a file
            if str(spec.get("text", "")).startswith("@"):
                spec["text"] = Path(spec["text"][1:]).read_text(encoding="utf-8")
        report = await run_prompt_comparison(raw, root_agent=root_agent, items=_csv(args.items) or None, limit=args.limit,
                                             evalset=args.evalset, metrics=args.metrics, judge=args.judge, retry_errors=args.retry_errors)
    except CompareConfigError as exc:
        print("Invalid comparison:\n  - " + "\n  - ".join(exc.problems))
        return 2

    base = Path(args.out) if args.out else BACKEND_DIR / "reports" / f"prompt_compare_{time.strftime('%Y%m%d_%H%M%S')}"
    base.parent.mkdir(parents=True, exist_ok=True)
    base.with_suffix(".json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    base.with_suffix(".md").write_text(to_markdown(report), encoding="utf-8")
    print("\n" + to_markdown(report))
    print(f"report: {base.with_suffix('.md')}")
    return 0 if report["status"] == "compare_complete" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
