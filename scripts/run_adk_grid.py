"""Run a prompt-version x model grid on Google ADK's evaluators (ADK has no native way to do this).

    python scripts/run_adk_grid.py --versions v12,v13 --models openai/gpt-4o-mini,groq/openai/gpt-oss-120b
    python scripts/run_adk_grid.py --config grid.json --metrics fast
    python scripts/run_adk_grid.py --versions v1 --prompt-text poor=@poor_prompt.txt --models openai/gpt-4o-mini

Same config shape as the Langfuse grid ({"config": {...}} or flat). Cells run against the isolated SQLite
database, never the real one. `--metrics fast` makes no judge calls; `standard` adds final_response_match_v2.
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


def _print_report(report: dict) -> None:
    print(f"\n{report['status']}  engine={report['engine']}  evalset={report['evalset']}  metrics={report['metrics_preset']}  "
          f"judge={report['judge']}  {report['cells_succeeded']}/{report['cells_total']} cells  {report['duration_sec']}s")
    models = sorted({m for row in report["matrix"].values() for m in row})
    print(f"\n{'prompt':<14}" + "".join(f"{m.split('/')[-1][:24]:>26}" for m in models))
    for prompt, row in report["matrix"].items():
        print(f"{prompt:<14}" + "".join(f"{('n/a' if row.get(m) is None else f'{row[m]:.3f}'):>26}" for m in models))
    best = report.get("best")
    if best:
        print(f"\nbest: {best['prompt']} on {best['model']}  composite={best['composite']}  pass={best['pass_rate_percent']}%  "
              f"metrics={best['metrics']}")
    for cell in report["cells"]:
        if cell["status"] != "ok":
            print(f"  FAILED {cell['prompt']} / {cell['model']}: {cell.get('error')}")
    for warning in report["warnings"]:
        print(f"  warning: {warning}")


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="path to a grid JSON file (same shape as the Langfuse grid config)")
    parser.add_argument("--versions", help="root prompt versions, e.g. v12,v13")
    parser.add_argument("--labels", help="root prompt labels, e.g. live,baseline")
    parser.add_argument("--models", help="comma-separated models, e.g. openai/gpt-4o-mini,groq/openai/gpt-oss-120b")
    parser.add_argument("--items", help="comma-separated golden ids (default: every non-mutating case of the eval set)")
    parser.add_argument("--limit", type=int, help="use only the first N items")
    parser.add_argument("--judge", help="judge model for LLM-judged metrics (default: openai/gpt-4o-mini)")
    parser.add_argument("--prompt-text", action="append", default=[], metavar="TAG=TEXT|TAG=@FILE",
                        help="test literal prompt text under a tag (repeatable)")
    parser.add_argument("--evalset", choices=["deterministic", "golden"], default="deterministic")
    parser.add_argument("--metrics", choices=["fast", "standard", "full"], default="standard")
    parser.add_argument("--include-mutating", action="store_true", help="also run cases that write (apply leave, sync)")
    parser.add_argument("--run-prefix", default="adk-grid")
    parser.add_argument("--out", help="write the full JSON report here (default: reports/adk_grid_<time>.json)")
    args = parser.parse_args()

    root_agent = prepare_adk_runtime()
    from app.evaluations.grid_config import GridConfigError
    from app.optimization.adk_grid import run_adk_grid

    body = json.loads(Path(args.config).read_text(encoding="utf-8")) if args.config else {"config": {}}
    cfg = body["config"] if isinstance(body.get("config"), dict) else body
    for key, value in (("prompt_versions", _csv(args.versions)), ("prompt_labels", _csv(args.labels)),
                       ("models", _csv(args.models)), ("items", _csv(args.items))):
        if value:
            cfg[key] = value
    if args.limit:
        cfg["limit"] = args.limit
    if args.judge:
        cfg["judge"] = args.judge
    cfg.setdefault("run_prefix", args.run_prefix)
    texts = dict(cfg.get("prompt_texts") or {})
    for raw in args.prompt_text:
        tag, _, text = raw.partition("=")
        texts[tag] = Path(text[1:]).read_text(encoding="utf-8") if text.startswith("@") else text
    if texts:
        cfg["prompt_texts"] = texts

    try:
        report = await run_adk_grid(body, root_agent=root_agent, evalset=args.evalset, metrics=args.metrics,
                                    include_mutating=args.include_mutating)
    except GridConfigError as exc:
        print("Invalid grid config:\n  - " + "\n  - ".join(exc.problems))
        return 2

    _print_report(report)
    out = Path(args.out) if args.out else BACKEND_DIR / "reports" / f"adk_grid_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nfull report: {out}")
    return 0 if report["status"] == "grid_complete" else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
