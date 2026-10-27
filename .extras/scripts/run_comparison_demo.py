"""
Prompt & Model Comparison Runner for Langfuse Experiments
=========================================================
Runs an automated A/B evaluation against the Golden Benchmark dataset:
- Run 1 (Baseline): Groq GPT-OSS-120B with Prompt v1
- Run 2 (Challenger): Gemini 3.8 Flash with Prompt v13

Uploads evaluation scores to Langfuse Cloud for side-by-side comparison.
"""
import asyncio
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.dataset_sync_service import langfuse_dataset_service

async def main():
    print("=" * 70)
    print("  PEOPLEOPS: A/B PROMPT & MODEL EXPERIMENT COMPARISON")
    print("=" * 70)
    print("\nStarting comparison experiment (2 benchmark prompts per run for quick demo)...")

    results = await langfuse_dataset_service.run_comparison_experiment(
        baseline={
            "model_name": "groq/openai/gpt-oss-120b",
            "prompt_name": "peopleops-root-orchestrator",
            "prompt_version": 1,
            "run_name": "baseline-gpt120b-prompt-v1"
        },
        challenger={
            "model_name": "gemini-3.8-flash",
            "prompt_name": "peopleops-root-orchestrator",
            "prompt_version": 13,
            "run_name": "challenger-gemini-prompt-v13"
        },
        limit=2
    )

    print("\n" + "=" * 70)
    print("  EXPERIMENT RESULTS")
    print("=" * 70)
    b = results["baseline"]
    c = results["challenger"]
    summary = results["comparison_summary"]

    print(f"\n[BASELINE]   Model: {b['model']} | Prompt: {b['prompt']}")
    print(f"             Pass Rate: {b['pass_rate']} | Score: {b['avg_score']} | Time: {b['duration_sec']}s")
    print(f"             Run URL:   {b['url']}")

    print(f"\n[CHALLENGER] Model: {c['model']} | Prompt: {c['prompt']}")
    print(f"             Pass Rate: {c['pass_rate']} | Score: {c['avg_score']} | Time: {c['duration_sec']}s")
    print(f"             Run URL:   {c['url']}")

    print(f"\n[SUMMARY]    Winner:     {summary['winner']}")
    print(f"             Score Delta: {summary['score_delta']:+}")
    print(f"             Pass Delta:  {summary['pass_rate_delta']}")
    print(f"\n👉 Compare side-by-side in Langfuse UI:")
    print(f"   {summary['langfuse_experiments_url']}")

if __name__ == "__main__":
    asyncio.run(main())
