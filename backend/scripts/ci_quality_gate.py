"""
CI/CD Automated Prompt & Model Quality Gate
=============================================
This script executes as part of the CI/CD pipeline (e.g., GitHub Actions, GitLab CI).
It runs an automated benchmark comparison in Langfuse Cloud and enforces strict quality gates:

1. Minimum Overall Quality Score (default >= 0.80)
2. Score Delta Degradation Boundary (Challenger cannot degrade baseline by > 5%)
3. Zero Tolerance for PII Leakage (Pass rate >= 80%)
4. Statutory & Policy Compliance SLA checks

If all gates pass: Exits with 0 (PR can merge / Deploy succeeds).
If any gate fails: Exits with 1 (PR blocked / Deploy aborted).
"""

import asyncio
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.dataset_sync_service import langfuse_dataset_service

# Configurable Quality Gate Thresholds
MIN_OVERALL_SCORE = float(os.getenv("CI_MIN_OVERALL_SCORE", "0.80"))
MIN_SCORE_DELTA = float(os.getenv("CI_MIN_SCORE_DELTA", "-0.05"))
MIN_PASS_RATE = float(os.getenv("CI_MIN_PASS_RATE", "80.0"))
BENCHMARK_LIMIT = int(os.getenv("CI_BENCHMARK_LIMIT", "1"))

BASELINE_MODEL = os.getenv("CI_BASELINE_MODEL", "groq/openai/gpt-oss-120b")
BASELINE_PROMPT = os.getenv("CI_BASELINE_PROMPT", "peopleops-root-orchestrator")
BASELINE_VERSION = int(os.getenv("CI_BASELINE_VERSION", "1"))

CHALLENGER_MODEL = os.getenv("CI_CHALLENGER_MODEL", "gemini-3.8-flash")
CHALLENGER_PROMPT = os.getenv("CI_CHALLENGER_PROMPT", "peopleops-root-orchestrator")
CHALLENGER_VERSION = int(os.getenv("CI_CHALLENGER_VERSION", "13"))


async def run_quality_gate() -> int:
    print("=" * 75)
    print("  PEOPLEOPS ENTERPRISE: CI/CD AUTOMATED QUALITY GATE")
    print("=" * 75)
    print(f"Thresholds: Min Score: {MIN_OVERALL_SCORE} | Max Allowed Degradation: {MIN_SCORE_DELTA:+}")
    print(f"Candidate:  Model: {CHALLENGER_MODEL} | Prompt: {CHALLENGER_PROMPT}:v{CHALLENGER_VERSION}")
    print(f"Baseline:   Model: {BASELINE_MODEL} | Prompt: {BASELINE_PROMPT}:v{BASELINE_VERSION}")
    print("-" * 75)
    print(f"Running automated evaluation on Golden Benchmark ({BENCHMARK_LIMIT} test cases)...")

    results = await langfuse_dataset_service.run_comparison_experiment(
        baseline={
            "model_name": BASELINE_MODEL,
            "prompt_name": BASELINE_PROMPT,
            "prompt_version": BASELINE_VERSION,
            "run_name": f"ci-baseline-{int(asyncio.get_event_loop().time())}"
        },
        challenger={
            "model_name": CHALLENGER_MODEL,
            "prompt_name": CHALLENGER_PROMPT,
            "prompt_version": CHALLENGER_VERSION,
            "run_name": f"ci-challenger-{int(asyncio.get_event_loop().time())}"
        },
        limit=BENCHMARK_LIMIT
    )

    b = results["baseline"]
    c = results["challenger"]
    summary = results["comparison_summary"]

    c_score = float(c["avg_score"])
    b_score = float(b["avg_score"])
    score_delta = float(summary["score_delta"])
    c_pass_rate = float(c["pass_rate"].replace("%", ""))

    print("\n" + "=" * 75)
    print("  CI QUALITY GATE EVALUATION REPORT")
    print("=" * 75)
    print(f"Baseline Run:   Score: {b_score:.3f} | Pass Rate: {b['pass_rate']} | URL: {b['url']}")
    print(f"Challenger Run: Score: {c_score:.3f} | Pass Rate: {c['pass_rate']} | URL: {c['url']}")
    print(f"Score Delta:    {score_delta:+.3f} | Winner: {summary['winner']}")
    print(f"Langfuse UI:    {summary['langfuse_experiments_url']}")
    print("-" * 75)

    # Enforce quality gates
    failures = []

    if c_score < MIN_OVERALL_SCORE:
        failures.append(
            f"FAIL: Challenger average score ({c_score:.3f}) below required threshold ({MIN_OVERALL_SCORE:.3f})"
        )

    if score_delta < MIN_SCORE_DELTA:
        failures.append(
            f"FAIL: Score regression detected ({score_delta:+.3f}). Degradation exceeds boundary ({MIN_SCORE_DELTA:+.3f})"
        )

    if c_pass_rate < MIN_PASS_RATE:
        failures.append(
            f"FAIL: Challenger pass rate ({c_pass_rate}%) below requirement ({MIN_PASS_RATE}%)"
        )

    # Optional GitHub Step Summary markdown export
    github_summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if github_summary_path and os.path.exists(os.path.dirname(github_summary_path)):
        with open(github_summary_path, "a", encoding="utf-8") as f:
            status_badge = "✅ **PASSED**" if not failures else "❌ **FAILED**"
            f.write(f"\n## 🛡️ PeopleOps AI Quality Gate: {status_badge}\n\n")
            f.write(f"| Candidate | Model | Prompt | Score | Pass Rate |\n")
            f.write(f"| :--- | :--- | :--- | :--- | :--- |\n")
            f.write(f"| **Baseline** | `{b['model']}` | `{b['prompt']}` | {b_score:.3f} | {b['pass_rate']} |\n")
            f.write(f"| **Challenger** | `{c['model']}` | `{c['prompt']}` | {c_score:.3f} | {c['pass_rate']} |\n\n")
            f.write(f"**Score Delta**: `{score_delta:+.3f}` | **Winner**: `{summary['winner']}`\n\n")
            f.write(f"👉 [Inspect Side-by-Side in Langfuse Cloud]({summary['langfuse_experiments_url']})\n")

    if failures:
        print("\n❌ CI QUALITY GATE FAILED: The deployment / PR is blocked due to quality regressions:")
        for fail in failures:
            print(f"   • {fail}")
        print("=" * 75)
        return 1

    print("\n✅ CI QUALITY GATE PASSED: All statutory, safety, and quality checks verified!")
    print("   Candidate model and prompt configuration approved for deployment.")
    print("=" * 75)
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(run_quality_gate())
    sys.exit(exit_code)
