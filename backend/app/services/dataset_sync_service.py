"""PeopleOps — Langfuse Golden Dataset & Experiment Runner Service.
=================================================================
Manages permanent 25-prompt Golden Datasets in Langfuse Cloud, executes
automated benchmark experiments, and computes aggregate metrics across runs.
"""

from typing import Any, Dict, List, Optional
import time
import json
import os

from app.core.config import settings
from app.evaluations.golden_dataset_25 import GOLDEN_BENCHMARK_25, GoldenTestCase
from app.evaluations.llm_judge_service import llm_judge_service, JudgeEvaluationResult

try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False


DATASET_NAME = "peopleops-golden-benchmark-25"


class LangfuseDatasetSyncService:
    """Manages Langfuse Golden Datasets, Item Ingestion, and Experiment Runs."""

    def __init__(self):
        self._langfuse: Optional[Any] = None
        self._init_client()

    def _init_client(self):
        if LANGFUSE_AVAILABLE and settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            try:
                self._langfuse = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_BASE_URL or settings.LANGFUSE_HOST,
                )
            except Exception as e:
                print(f"Notice: Failed to initialize Langfuse for DatasetSync: {e}")
                self._langfuse = None

    def sync_golden_dataset_to_langfuse(self) -> Dict[str, Any]:
        """Creates or updates the 25-prompt Golden Dataset in Langfuse Cloud."""
        if not self._langfuse:
            return {"status": "skipped", "reason": "Langfuse credentials not configured", "items_count": len(GOLDEN_BENCHMARK_25)}

        try:
            # 1. Create dataset if it doesn't exist
            try:
                dataset = self._langfuse.create_dataset(
                    name=DATASET_NAME,
                    description="Permanent 25-Prompt Enterprise Golden Benchmark for PeopleOps HRMS Multi-Agent Fleet & NeMo Guardrails."
                )
            except Exception:
                # Dataset might already exist; fetch it
                try:
                    dataset = self._langfuse.get_dataset(name=DATASET_NAME)
                except Exception:
                    dataset = None

            # 2. Ingest 25 items
            synced_count = 0
            for tc in GOLDEN_BENCHMARK_25:
                item_payload = {
                    "prompt": tc.prompt,
                    "category": tc.category,
                    "expected_agent": tc.expected_agent,
                    "statutory_clause": tc.statutory_clause,
                    "must_contain_keywords": tc.must_contain_keywords,
                    "forbidden_terms": tc.forbidden_terms,
                    "test_id": tc.test_id,
                }
                expected_output = {
                    "reference": tc.reference_answer,
                    "expected_agent": tc.expected_agent,
                    "statutory_clause": tc.statutory_clause
                }

                try:
                    self._langfuse.create_dataset_item(
                        dataset_name=DATASET_NAME,
                        input=item_payload,
                        expected_output=expected_output,
                        metadata=tc.metadata
                    )
                    synced_count += 1
                except Exception as e:
                    # Item might exist, continue
                    synced_count += 1

            self._langfuse.flush()
            return {
                "status": "success",
                "dataset_name": DATASET_NAME,
                "synced_items": synced_count,
                "total_items": len(GOLDEN_BENCHMARK_25)
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "items_count": len(GOLDEN_BENCHMARK_25)}

    async def run_golden_benchmark_experiment(
        self,
        experiment_run_name: Optional[str] = None,
        db_session: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Runs all 25 benchmark prompts through the multi-agent system, evaluates with LLM-as-a-Judge,

        and records the complete experiment run in Langfuse Cloud.
        """
        from app.agents.orchestrator import llm_root_orchestrator
        from app.models.user import User, UserRole

        run_id = f"EXP-25-BENCHMARK-{int(time.time())}"
        run_name = experiment_run_name or run_id
        start_time_all = time.time()

        # Synthetic user for benchmark (Aarav Sharma)
        test_user = User(
            id="EMP-004",
            email="aarav.sharma@intelera.com",
            full_name="Aarav Sharma",
            role=UserRole.EMPLOYEE,
            is_active=True
        )

        results = []
        total_score_sum = 0.0
        passed_count = 0

        for tc in GOLDEN_BENCHMARK_25:
            t0 = time.perf_counter()
            session_id = f"sess_bench_{tc.test_id.lower()}_{int(time.time())}"
            
            try:
                chat_res = await llm_root_orchestrator.process_message(
                    db=db_session,
                    user=test_user,
                    message=tc.prompt,
                    session_id=session_id
                )
                duration_ms = (time.perf_counter() - t0) * 1000
                response_text = chat_res.response

                # Run LLM-as-a-Judge evaluation
                eval_res: JudgeEvaluationResult = llm_judge_service.evaluate_response(
                    query=tc.prompt,
                    response_text=response_text,
                    trace_id=getattr(chat_res, "session_id", session_id),
                    session_id=session_id,
                    expected_keywords=tc.must_contain_keywords,
                    forbidden_terms=tc.forbidden_terms,
                    statutory_clause=tc.statutory_clause,
                    latency_ms=duration_ms,
                    agent_name=chat_res.agent_routed,
                    push_to_langfuse=True
                )

                if eval_res.passed:
                    passed_count += 1
                total_score_sum += eval_res.overall_score

                results.append({
                    "id": tc.id,
                    "test_id": tc.test_id,
                    "category": tc.category,
                    "prompt": tc.prompt,
                    "agent_routed": chat_res.agent_routed,
                    "response_preview": response_text[:120].replace("\n", " "),
                    "latency_ms": round(duration_ms, 1),
                    "overall_score": eval_res.overall_score,
                    "passed": eval_res.passed,
                    "metrics": eval_res.metrics,
                    "feedback": eval_res.feedback
                })

            except Exception as e:
                duration_ms = (time.perf_counter() - t0) * 1000
                results.append({
                    "id": tc.id,
                    "test_id": tc.test_id,
                    "category": tc.category,
                    "prompt": tc.prompt,
                    "error": str(e),
                    "passed": False,
                    "overall_score": 0.0,
                    "latency_ms": round(duration_ms, 1)
                })

        total_duration = round(time.time() - start_time_all, 2)
        total_cases = len(GOLDEN_BENCHMARK_25)
        avg_score = round(total_score_sum / max(1, total_cases), 3)
        pass_rate = round((passed_count / max(1, total_cases)) * 100, 1)

        summary = {
            "run_id": run_id,
            "run_name": run_name,
            "dataset_name": DATASET_NAME,
            "total_cases": total_cases,
            "passed_cases": passed_count,
            "failed_cases": total_cases - passed_count,
            "pass_rate_percent": pass_rate,
            "average_overall_score": avg_score,
            "total_duration_sec": total_duration,
            "results": results
        }

        # Flush all scores and observations to Langfuse
        if self._langfuse:
            try:
                self._langfuse.flush()
            except Exception:
                pass

        return summary


langfuse_dataset_service = LangfuseDatasetSyncService()
