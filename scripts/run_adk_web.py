"""Start Google ADK Web for the PeopleOps agents.

    python scripts/run_adk_web.py [--port 8010]

Opens the ADK dev UI (chat, event trace, and the Eval tab) on the same agent fleet the backend runs.
The agent package (`adk_web/peopleops/agent.py`) forces an isolated local SQLite database, so tool calls
such as "apply leave" or "log hours" never touch the real database. Prompts still come from Langfuse.

Eval tab: choose an eval set (`peopleops_deterministic` or `peopleops_golden`) and run it with ADK's
built-in evaluators (tool trajectory, response match, final_response_match_v2, rubric-based response and tool
quality, hallucinations). Judge-based criteria need a judge model: `eval_config.json` uses openai/gpt-4o-mini.
See docs/04_adk_web_and_evaluation.md.
"""
import argparse
import importlib.util
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
AGENTS_DIR = BACKEND_DIR / "adk_web"
REQUIRED = {"pandas": "pandas", "tabulate": "tabulate", "rouge_score": "rouge-score"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Start ADK Web for the PeopleOps agents")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--model", help="Model for the agents, e.g. openai/gpt-4o-mini (default: the backend's provider)")
    parser.add_argument("--log-level", default="info", choices=["debug", "info", "warning", "error", "critical"])
    args = parser.parse_args()

    missing = [pip for module, pip in REQUIRED.items() if importlib.util.find_spec(module) is None]
    if missing:
        print(f"Missing packages for ADK evaluation: {', '.join(missing)}\n  pip install -r backend/requirements.txt")
        return 1

    os.environ["PYTHONPATH"] = os.pathsep.join(filter(None, [str(BACKEND_DIR), os.environ.get("PYTHONPATH")]))
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    if args.model:
        os.environ["ADK_WEB_MODEL"] = args.model
    os.chdir(BACKEND_DIR)

    from google.adk.cli import main as adk_main

    print(f"ADK Web -> http://localhost:{args.port}   (agents: {AGENTS_DIR})")
    print("Database: isolated SQLite (backend/data/adk_web.db); the real database is not used.")
    adk_main(["web", "--port", str(args.port), "--log_level", args.log_level, str(AGENTS_DIR)], prog_name="adk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
