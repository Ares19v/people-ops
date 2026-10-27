"""Regenerate the ADK eval sets and criteria config from the golden benchmark.

    python scripts/build_adk_evalset.py

Writes, next to the ADK Web agent:
  adk_web/peopleops/peopleops_golden.evalset.json         all 25 golden cases (with per-case rubrics)
  adk_web/peopleops/peopleops_deterministic.evalset.json  only cases whose tool arguments are fixed by the question
  adk_web/peopleops/eval_config.json                      ADK criteria for `adk eval --config_file_path`

The Eval tab in ADK Web lists every `*.evalset.json` in the agent folder. Run it after changing the golden
dataset or `app/evaluations/adk_expectations.py`.
"""
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.evaluations.adk_expectations import build_eval_config, to_eval_set  # noqa: E402

TARGET = BACKEND_DIR / "adk_web" / "peopleops"


def main() -> None:
    for eval_set_id, deterministic_only in (("peopleops_golden", False), ("peopleops_deterministic", True)):
        document = to_eval_set(eval_set_id=eval_set_id, deterministic_only=deterministic_only)
        (TARGET / f"{eval_set_id}.evalset.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        print(f"{eval_set_id}.evalset.json: {len(document['eval_cases'])} cases")
    (TARGET / "eval_config.json").write_text(json.dumps(build_eval_config(), indent=2) + "\n", encoding="utf-8")
    print("eval_config.json written")


if __name__ == "__main__":
    main()
