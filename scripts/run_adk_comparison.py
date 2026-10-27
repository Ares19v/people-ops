"""Compare Google ADK's evaluators with the Langfuse pipeline on the same golden cases.

    python scripts/run_adk_comparison.py [--cases ID1,ID2] [--limit 6] [--model openai/gpt-4o-mini]
                                          [--judge openai/gpt-4o-mini] [--json-out report.json]

Runs on an isolated SQLite database (so cases that apply leave / log hours / sync Zoho are safe to include),
then prints a per-case table (every ADK evaluator) and the aggregates. The Langfuse leg creates an experiment run in your Langfuse
project and the ADK scores are attached to that run. See docs/04_adk_web_and_evaluation.md.
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Isolation must be in place before the app is imported (the settings read it at import time).
_db_file = Path(os.environ.get("ADK_COMPARE_DB_FILE") or (BACKEND_DIR / "data" / "adk_compare.db")).resolve()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_file.as_posix()}"
os.environ["SYNC_DATABASE_URL"] = f"sqlite:///{_db_file.as_posix()}"
os.environ["ENVIRONMENT"] = os.environ.get("ADK_COMPARE_ENVIRONMENT", "adk-compare")
os.environ.setdefault("LLM_NUM_RETRIES", "5")  # wait out provider rate limits instead of returning empty answers


SMOKE_CASES = ["BENCH-01-LEAVE-BALANCES", "BENCH-11-TIMESHEET-UTILIZATION", "BENCH-22-NEMO-JAILBREAK-DEFENSE"]  # routing + a tool call + a guardrail case


def _fmt(value, width=5):
    return f"{value:.2f}".rjust(width) if isinstance(value, (int, float)) else "  n/a"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", help="comma-separated golden test ids (default: 3 representative cases)")
    parser.add_argument("--all", action="store_true", help="run all 25 golden cases (slow, and heavy on rate-limited providers)")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--model")
    parser.add_argument("--judge", help="LLM judge model, or 'heuristic' for keyword rules (default: openai/gpt-4o-mini if you have the key, else Groq)")
    parser.add_argument("--json-out")
    args = parser.parse_args()

    from app.core.database import Base, engine
    from data.seed_data import seed_initial_data
    from app.evaluations.adk_comparison import run_adk_langfuse_comparison
    from app.observability import langfuse_client

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await seed_initial_data()

    report = await run_adk_langfuse_comparison(
        None if args.all else ([c.strip() for c in args.cases.split(",")] if args.cases else SMOKE_CASES),
        model=args.model, judge=args.judge, limit=args.limit,
    )

    print(f"\nmodel={report['model']}  judge={report['judge']}  mock_mode={report['mock_mode']}  {report['duration_sec']}s")
    print(f"Langfuse run: {report['langfuse_run']['url']}")
    print(f"ADK judge: {report['adk_judge']}")
    columns = (
        "tool_trajectory_avg_score", "response_match_score", "final_response_match_v2",
        "rubric_based_final_response_quality_v1", "rubric_based_tool_use_quality_v1", "hallucinations_v1",
    )
    print(f"\n{'case':<32} {'LF':>5} {'pass':>5} | {'traj':>5} {'rouge':>5} {'match':>5} {'rubR':>5} {'rubT':>5} {'hall':>5} {'pass':>5} | agreement")
    for row in report["rows"]:
        lf, adk = row["langfuse"] or {}, row["adk"] or {}
        lf_cell = f"{_fmt(lf.get('overall_score'))} {str(lf.get('passed', '-')):>5}" if "error" not in lf else "  ERR"
        scores = adk.get("scores", {})
        if "error" in adk:
            adk_cell = "  ERR: " + adk["error"][:40]
        else:
            adk_cell = " ".join(_fmt(scores.get(m)) for m in columns) + f" {str(adk.get('passed', '-')):>5}"
        extra = f"  rubric-fails:{','.join(r.split(':')[1] for r in adk['failed_rubrics'])}" if adk.get("failed_rubrics") else ""
        print(f"{row['test_id']:<32} {lf_cell} | {adk_cell} | {row['agreement']}{extra}")
    agg = report["aggregate"]
    print("\nADK      : " + "  ".join(f"{k.split('_v')[0]} {v}" for k, v in agg["adk"]["metrics"].items()) +
          f"  | pass {agg['adk']['pass_rate']}  tokens {agg['adk']['total_tokens']}")
    print(f"Langfuse : overall {agg['langfuse']['overall_score']}  pass {agg['langfuse']['pass_rate']}")
    print(f"Agreement: {agg['agreement']}   correlation(LF overall, ADK rubric quality) = {agg['correlation']['langfuse_overall_vs_adk_rubric_quality']}")
    for warning in report["warnings"]:
        print("WARNING:", warning)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(report, indent=2, default=str))
    langfuse_client.flush()
    langfuse_client.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
