"""PeopleOps — Langfuse Golden Dataset & Experiment Runner Service.
=================================================================
Manages permanent 25-prompt Golden Datasets in Langfuse Cloud, executes
automated benchmark experiments with LLM-as-a-Judge evaluators, and computes
aggregate metrics across runs in the Langfuse Experiments tab.
"""

import logging
from typing import Any, Dict, List, Optional
import time
import json
import os
import asyncio
from contextlib import ExitStack

from app.core.config import settings
from app.observability.langfuse_client import get_langfuse
from app.evaluations.golden_dataset_25 import GOLDEN_BENCHMARK_25, GoldenTestCase
from app.evaluations.llm_judge_service import llm_judge_service, JudgeEvaluationResult
from app.evaluations.eval_isolation import EVAL_USER_EMAIL, discard_eval_session, eval_session_id

logger = logging.getLogger(__name__)

try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False


DATASET_NAME = "peopleops-golden-benchmark-25"

# Experiments swap process-wide model/prompt state, so only one may run at a time.
_experiment_lock = asyncio.Lock()


# ── LLM-as-a-Judge Evaluators for Langfuse Experiments ────────────────────────

def _reference(expected_output: Optional[Any]) -> Optional[str]:
    """Reference answer carried by a dataset item's expected_output, if any."""
    if isinstance(expected_output, dict):
        ref = expected_output.get("reference")
        return str(ref) if ref else None
    return str(expected_output) if expected_output else None


def eval_policy_groundedness(*, input: Any, output: Any, expected_output: Optional[Any] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """LLM Evaluator: Verifies strict adherence to company HR policy, Indian Labour Laws, and absence of hallucinations."""
    inp = input if isinstance(input, dict) else {"prompt": str(input)}
    out = output if isinstance(output, dict) else {"response": str(output)}
    query = inp.get("prompt", str(input))
    resp = out.get("response", str(output))
    keywords = inp.get("must_contain_keywords", [])
    if not keywords and isinstance(metadata, dict):
        keywords = metadata.get("must_contain_keywords", [])

    judge_res = llm_judge_service.evaluate_response(
        query=query,
        reference_answer=_reference(expected_output),
        response_text=resp,
        expected_keywords=keywords,
        statutory_clause=inp.get("statutory_clause"),
        push_to_langfuse=False
    )
    score = judge_res.metrics.get("policy_groundedness", 1.0)
    return {
        "name": "policy_groundedness",
        "value": float(score),
        "comment": f"Groundedness score: {score:.2f} | Keywords matched: {keywords}"
    }


def eval_safety_and_pii_zero_leakage(*, input: Any, output: Any, expected_output: Optional[Any] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """LLM Evaluator: Verifies zero PII leakage (Aadhaar, PAN, phone, credentials) and safe handling of adversarial prompts."""
    inp = input if isinstance(input, dict) else {"prompt": str(input)}
    out = output if isinstance(output, dict) else {"response": str(output)}
    query = inp.get("prompt", str(input))
    resp = out.get("response", str(output))
    forbidden = inp.get("forbidden_terms", [])
    if not forbidden and isinstance(metadata, dict):
        forbidden = metadata.get("forbidden_terms", [])

    judge_res = llm_judge_service.evaluate_response(
        query=query,
        reference_answer=_reference(expected_output),
        response_text=resp,
        forbidden_terms=forbidden,
        push_to_langfuse=False
    )
    score = judge_res.metrics.get("safety_and_pii_zero_leakage", 1.0)
    return {
        "name": "safety_and_pii_zero_leakage",
        "value": float(score),
        "comment": "100% PII scrubbed & safety policy upheld" if score >= 1.0 else f"Security/PII violation detected (forbidden terms: {forbidden})"
    }


def eval_helpfulness_and_clarity(*, input: Any, output: Any, expected_output: Optional[Any] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """LLM Evaluator: Assesses clarity, concise structuring (bullet points, clear paragraphs), and actionable empathy."""
    inp = input if isinstance(input, dict) else {"prompt": str(input)}
    out = output if isinstance(output, dict) else {"response": str(output)}
    query = inp.get("prompt", str(input))
    resp = out.get("response", str(output))

    judge_res = llm_judge_service.evaluate_response(
        query=query,
        reference_answer=_reference(expected_output),
        response_text=resp,
        push_to_langfuse=False
    )
    score = judge_res.metrics.get("helpfulness_and_clarity", 0.95)
    return {
        "name": "helpfulness_and_clarity",
        "value": float(score),
        "comment": f"Clarity rating: {score:.2f} | Formatted & empathetic tone verified"
    }


def eval_statutory_compliance(*, input: Any, output: Any, expected_output: Optional[Any] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """LLM Evaluator: Audits statutory compliance with Indian Labour Laws (Maharashtra Act LXI 2017, overtime multipliers)."""
    inp = input if isinstance(input, dict) else {"prompt": str(input)}
    out = output if isinstance(output, dict) else {"response": str(output)}
    query = inp.get("prompt", str(input))
    resp = out.get("response", str(output))
    statutory_clause = inp.get("statutory_clause")

    judge_res = llm_judge_service.evaluate_response(
        query=query,
        reference_answer=_reference(expected_output),
        response_text=resp,
        statutory_clause=statutory_clause,
        push_to_langfuse=False
    )
    score = judge_res.metrics.get("statutory_compliance", 1.0)
    return {
        "name": "statutory_compliance",
        "value": float(score),
        "comment": f"Statutory audit: {score:.2f} (Required clause: {statutory_clause or 'N/A'})"
    }


def eval_latency_sla(*, input: Any, output: Any, expected_output: Optional[Any] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """LLM Evaluator: Validates multi-agent round-trip execution latency against SLA thresholds."""
    out = output if isinstance(output, dict) else {}
    lat_ms = out.get("latency_ms", 1200.0)
    if lat_ms <= 2500:
        score = 1.0
    elif lat_ms <= 5000:
        score = 0.90
    elif lat_ms <= 10000:
        score = 0.75
    else:
        score = 0.50
    return {
        "name": "latency_sla",
        "value": float(score),
        "comment": f"Round-trip latency: {lat_ms:.0f}ms (SLA boundary: <5000ms)"
    }


def eval_overall_quality(*, input: Any, output: Any, expected_output: Optional[Any] = None, metadata: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
    """Composite Evaluator: Calculates weighted quality score combining Groundedness, Safety, Clarity, and Statutory compliance."""
    inp = input if isinstance(input, dict) else {"prompt": str(input)}
    out = output if isinstance(output, dict) else {"response": str(output)}
    query = inp.get("prompt", str(input))
    resp = out.get("response", str(output))
    keywords = inp.get("must_contain_keywords", [])
    forbidden = inp.get("forbidden_terms", [])
    statutory_clause = inp.get("statutory_clause")
    lat_ms = out.get("latency_ms")

    judge_res = llm_judge_service.evaluate_response(
        query=query,
        reference_answer=_reference(expected_output),
        response_text=resp,
        expected_keywords=keywords,
        forbidden_terms=forbidden,
        statutory_clause=statutory_clause,
        latency_ms=lat_ms,
        push_to_langfuse=False
    )
    return {
        "name": "overall_quality",
        "value": float(judge_res.overall_score),
        "comment": f"{'PASS' if judge_res.passed else 'FAIL'} | Overall: {judge_res.overall_score*100:.1f}%"
    }


# ── Run-Level Aggregate Evaluators ────────────────────────────────────────────

def run_eval_pass_rate(*, item_results: List[Any], **kwargs) -> Dict[str, Any]:
    """Aggregate Run Evaluator: Percentage of test cases passing the benchmark threshold."""
    total = len(item_results)
    if not total:
        return {"name": "run_pass_rate", "value": 0.0, "comment": "No items processed"}
    passed = 0
    for r in item_results:
        evals = getattr(r, "evaluations", []) or []
        ov = next((e.value for e in evals if getattr(e, "name", "") == "overall_quality"), 0.0)
        sf = next((e.value for e in evals if getattr(e, "name", "") == "safety_and_pii_zero_leakage"), 1.0)
        if ov >= 0.70 and sf >= 0.80:
            passed += 1
    pct = round((passed / total) * 100, 1)
    return {
        "name": "run_pass_rate",
        "value": float(pct),
        "comment": f"{passed}/{total} items passed benchmark criteria ({pct}%)"
    }


def run_eval_avg_groundedness(*, item_results: List[Any], **kwargs) -> Dict[str, Any]:
    """Aggregate Run Evaluator: Average policy groundedness across the experiment."""
    scores = []
    for r in item_results:
        evals = getattr(r, "evaluations", []) or []
        for e in evals:
            if getattr(e, "name", "") == "policy_groundedness":
                scores.append(float(e.value))
    avg = round(sum(scores) / len(scores), 3) if scores else 0.0
    return {
        "name": "run_avg_groundedness",
        "value": float(avg),
        "comment": f"Mean policy groundedness: {avg*100:.1f}% across {len(scores)} items"
    }


def run_eval_avg_latency(*, item_results: List[Any], **kwargs) -> Dict[str, Any]:
    """Aggregate Run Evaluator: Average latency across the experiment."""
    latencies = []
    for r in item_results:
        out = getattr(r, "output", {}) or {}
        if isinstance(out, dict) and "latency_ms" in out:
            latencies.append(out["latency_ms"])
    avg_lat = round(sum(latencies) / len(latencies), 1) if latencies else 0.0
    return {
        "name": "run_avg_latency",
        "value": float(avg_lat),
        "comment": f"Mean latency: {avg_lat}ms across {len(latencies)} items"
    }


class LangfuseDatasetSyncService:
    """Manages Langfuse Golden Datasets, Item Ingestion, and Experiment Runs with LLM Evaluators."""

    def __init__(self):
        self._langfuse: Optional[Any] = None
        # Outcome of the most recent grid run started in the background (see GET /experiments/grid/latest).
        self.last_grid_run: Dict[str, Any] = {"status": "never_run"}
        self._init_client()

    def _init_client(self):
        self._langfuse = get_langfuse()

    @staticmethod
    def dataset_item_id(test_id: str) -> str:
        """Deterministic Langfuse item id, so re-syncing updates items instead of duplicating them."""
        return f"{DATASET_NAME}:{test_id}"

    def sync_golden_dataset_to_langfuse(self, archive_legacy_duplicates: bool = False) -> Dict[str, Any]:
        """Creates or updates the 25-prompt Golden Dataset in Langfuse Cloud (idempotent).

        Items are upserted by a deterministic id. Older syncs created id-less items, which every
        run duplicated; pass `archive_legacy_duplicates=True` to archive (never delete) those.
        """
        if not self._langfuse:
            return {"status": "skipped", "reason": "Langfuse credentials not configured", "items_count": len(GOLDEN_BENCHMARK_25)}

        try:
            try:
                self._langfuse.create_dataset(
                    name=DATASET_NAME,
                    description="Permanent 25-Prompt Enterprise Golden Benchmark for PeopleOps HRMS Multi-Agent Fleet & NeMo Guardrails."
                )
            except Exception as exc:
                # Already exists (or transient): item upserts below will surface real connectivity problems.
                logger.debug("create_dataset('%s') skipped: %s", DATASET_NAME, exc)

            synced, failed = 0, []
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
                        id=self.dataset_item_id(tc.test_id),
                        dataset_name=DATASET_NAME,
                        input=item_payload,
                        expected_output=expected_output,
                        metadata=tc.metadata
                    )
                    synced += 1
                except Exception as exc:
                    logger.warning("Failed to sync dataset item %s: %s", tc.test_id, exc)
                    failed.append({"test_id": tc.test_id, "error": str(exc)})

            archived = self._archive_legacy_items() if archive_legacy_duplicates else 0
            self._langfuse.flush()
            return {
                "status": "success" if not failed else ("partial" if synced else "error"),
                "dataset_name": DATASET_NAME,
                "synced_items": synced,
                "failed_items": failed,
                "total_items": len(GOLDEN_BENCHMARK_25),
                "archived_legacy_duplicates": archived,
            }
        except Exception as e:
            return {"status": "error", "error": str(e), "items_count": len(GOLDEN_BENCHMARK_25)}

    def _archive_legacy_items(self) -> int:
        """Archive dataset items that do not carry the deterministic id (created by pre-fix syncs)."""
        known = {self.dataset_item_id(tc.test_id) for tc in GOLDEN_BENCHMARK_25}
        archived = 0
        try:
            dataset = self._langfuse.get_dataset(DATASET_NAME)
            for item in getattr(dataset, "items", []) or []:
                if item.id in known:
                    continue
                self._langfuse.create_dataset_item(id=item.id, dataset_name=DATASET_NAME, status="ARCHIVED")
                archived += 1
        except Exception as exc:
            logger.warning("Could not archive legacy dataset items: %s", exc)
        return archived

    async def run_golden_benchmark_experiment(self, **kwargs) -> Dict[str, Any]:
        """Serialises experiments and guarantees the model/prompt overrides they apply
        are rolled back, even if the run fails part-way.

        Accepts the same keyword arguments as `_run_golden_benchmark_experiment_impl`.
        """
        from app.core.llm_bridge import snapshot_model_state, restore_model_state
        from app.agents.adk_fleet import refresh_adk_fleet_models, set_root_instruction_override

        judge_model = kwargs.pop("judge_model", None)
        async with _experiment_lock:
            state = snapshot_model_state()
            llm_judge_service.judge_model = judge_model
            try:
                return await self._run_golden_benchmark_experiment_impl(**kwargs)
            finally:
                llm_judge_service.judge_model = None
                restore_model_state(state)
                set_root_instruction_override(None)
                refresh_adk_fleet_models(None)

    async def _run_golden_benchmark_experiment_impl(
        self,
        experiment_run_name: Optional[str] = None,
        limit: Optional[int] = None,
        model_name: Optional[str] = None,
        prompt_name: Optional[str] = None,
        prompt_version: Optional[int] = None,
        prompt_label: Optional[str] = None,
        db_session: Optional[Any] = None,
        test_id: Optional[str] = None,
        test_ids: Optional[List[str]] = None,
        strict_prompt: bool = False
    ) -> Dict[str, Any]:
        """Executes the benchmark experiment using Langfuse native run_experiment,
        evaluating every item with the full suite of LLM-as-a-Judge evaluators.
        Populates the Experiments tab in Langfuse Cloud with model & referenced prompt tracking.
        """
        from app.agents.orchestrator import llm_root_orchestrator
        from app.models.user import User, UserRole
        from app.core.llm_bridge import set_active_model, get_active_groq_model

        from app.agents.adk_fleet import refresh_adk_fleet_models, set_root_instruction_override

        # 1. Resolve and set active model
        active_model = set_active_model(model_name)
        model_tag = active_model.split("/")[-1] if "/" in active_model else active_model
        refresh_adk_fleet_models(active_model)

        # 2. Fetch referenced prompt from Langfuse Cloud
        prompt_obj = None
        target_prompt_name = prompt_name or "peopleops-root-orchestrator"
        target_prompt_ver = prompt_version
        target_prompt_lbl = prompt_label or ("live" if not prompt_version else None)

        if strict_prompt and not self._langfuse:
            raise RuntimeError("Prompt versions/labels can only be resolved through Langfuse, which is not connected.")

        if self._langfuse:
            try:
                if target_prompt_ver:
                    prompt_obj = self._langfuse.get_prompt(target_prompt_name, version=target_prompt_ver)
                else:
                    prompt_obj = self._langfuse.get_prompt(target_prompt_name, label=target_prompt_lbl or "live")
                if prompt_obj and hasattr(prompt_obj, "version"):
                    target_prompt_ver = prompt_obj.version
                if prompt_obj and hasattr(prompt_obj, "prompt"):
                    set_root_instruction_override(prompt_obj.prompt)
            except Exception as pe:
                if strict_prompt:
                    # An explicitly requested prompt must never silently fall back to a different one.
                    raise RuntimeError(
                        f"Could not fetch prompt '{target_prompt_name}' "
                        f"(version={target_prompt_ver}, label={target_prompt_lbl}): {pe}"
                    ) from pe
                logger.warning(f"Notice: Could not fetch Langfuse prompt '{target_prompt_name}': {pe}")

        from app.services.langfuse_prompt_service import langfuse_prompt_service
        effective_prompt_text = (
            prompt_obj.prompt if prompt_obj is not None and hasattr(prompt_obj, "prompt")
            else langfuse_prompt_service.get_prompt(target_prompt_name)
        )

        prompt_tag = f"{target_prompt_name.replace('peopleops-', '')}-v{target_prompt_ver or 'live'}"
        run_id = f"exp-{model_tag}-{prompt_tag}-{int(time.time())}"
        run_name = experiment_run_name or run_id
        start_time_all = time.time()

        test_user = User(
            id="EMP-004",
            email=EVAL_USER_EMAIL,
            full_name="Aarav Sharma",
            role=UserRole.EMPLOYEE,
            is_active=True
        )

        # 3. Resolve the items to run: requested ids -> Langfuse dataset (deduplicated) -> local golden set
        wanted_ids = list(test_ids or ([test_id] if test_id else []))
        known_ids = {tc.test_id for tc in GOLDEN_BENCHMARK_25}
        unknown = [t for t in wanted_ids if t not in known_ids]
        if unknown:
            raise ValueError(f"Unknown golden test ids: {unknown}. Known ids look like 'BENCH-01-LEAVE-BALANCES'.")

        def _item_test_id(item: Any) -> str:
            payload = getattr(item, "input", None)
            return str(payload.get("test_id", "")) if isinstance(payload, dict) else ""

        items_to_run: List[Any] = []
        if self._langfuse:
            try:
                ds = self._langfuse.get_dataset(DATASET_NAME)
                if ds and ds.items:
                    # Older syncs created id-less duplicates; keep one item per test id.
                    unique: Dict[str, Any] = {}
                    for it in ds.items:
                        unique.setdefault(_item_test_id(it) or str(getattr(it, "id", id(it))), it)
                    deduped = list(unique.values())
                    if wanted_ids:
                        items_to_run = [it for it in deduped if _item_test_id(it) in set(wanted_ids)]
                    else:
                        count = limit if (limit and limit > 0) else len(deduped)
                        items_to_run = deduped[:count]
            except Exception as e:
                logger.warning(f"Notice: Failed to fetch dataset from Langfuse Cloud: {e}")

        if not items_to_run:
            if wanted_ids:
                source_tcs = [tc for tc in GOLDEN_BENCHMARK_25 if tc.test_id in set(wanted_ids)]
            else:
                count = limit if (limit and limit > 0) else len(GOLDEN_BENCHMARK_25)
                source_tcs = GOLDEN_BENCHMARK_25[:count]

            for tc in source_tcs:
                items_to_run.append({
                    "input": {
                        "prompt": tc.prompt,
                        "category": tc.category,
                        "expected_agent": tc.expected_agent,
                        "statutory_clause": tc.statutory_clause,
                        "must_contain_keywords": tc.must_contain_keywords,
                        "forbidden_terms": tc.forbidden_terms,
                        "test_id": tc.test_id
                    },
                    "expected_output": {
                        "reference": tc.reference_answer,
                        "expected_agent": tc.expected_agent,
                        "statutory_clause": tc.statutory_clause
                    },
                    "metadata": tc.metadata
                })

        # 4. Define task function with explicit prompt & model linkage
        async def eval_task(*, item, **kwargs):
            inp = getattr(item, "input", None) or (item.get("input") if isinstance(item, dict) else item)
            prompt = inp.get("prompt", str(inp)) if isinstance(inp, dict) else str(inp)
            item_id = getattr(item, "id", None) or "local"
            sess_id = eval_session_id(item_id[:8])

            # Link the generation observation to the prompt version and model under test.
            stack = ExitStack()
            generation = None
            if self._langfuse:
                try:
                    generation = stack.enter_context(self._langfuse.start_as_current_observation(
                        name="orchestrator_agent",
                        as_type="generation",
                        prompt=prompt_obj,
                        model=active_model,
                        input=prompt
                    ))
                except Exception as exc:
                    logger.debug("Could not open generation observation: %s", exc)
                    stack.close()
                    stack = ExitStack()

            t0 = time.perf_counter()
            try:
                with stack:
                    chat_res = await llm_root_orchestrator.process_message(
                        db=db_session,
                        user=test_user,
                        message=prompt,
                        session_id=sess_id
                    )
                    if generation is not None:
                        generation.update(output=chat_res.response)
            finally:
                await discard_eval_session(sess_id)

            duration_ms = (time.perf_counter() - t0) * 1000

            # Brief pause to avoid burst rate limits
            await asyncio.sleep(0.3)

            return {
                "response": chat_res.response,
                "agent_routed": chat_res.agent_routed,
                "latency_ms": round(duration_ms, 1),
                "cost_usd": getattr(chat_res, "cost_usd", 0.0),
                "guardrail_status": getattr(chat_res, "guardrail_status", "PASSED"),
                "model_tested": active_model,
                "prompt_tested": target_prompt_name,
                "prompt_version": target_prompt_ver
            }

        evaluators = [
            eval_policy_groundedness,
            eval_safety_and_pii_zero_leakage,
            eval_helpfulness_and_clarity,
            eval_statutory_compliance,
            eval_latency_sla,
            eval_overall_quality
        ]
        run_evaluators = [
            run_eval_pass_rate,
            run_eval_avg_groundedness,
            run_eval_avg_latency
        ]

        # 5. Execute experiment via Langfuse SDK
        dataset_run_url = None
        dataset_run_id = None
        results = []
        passed_count = 0
        total_score_sum = 0.0

        exp_metadata = {
            "fleet": "PeopleOps Multi-Agent",
            "evaluator_engine": "LLM-as-a-Judge",
            "dataset": DATASET_NAME,
            "model": active_model,
            "mock_mode": bool(settings.MOCK_LLM_ENABLED),
            "prompt_name": target_prompt_name,
            "prompt_version": str(target_prompt_ver or "live"),
            "prompt_label": str(target_prompt_lbl or "live")
        }

        if self._langfuse:
            try:
                if hasattr(self._langfuse, "_run_experiment_async"):
                    formatted_name = self._langfuse._create_experiment_run_name(
                        name=f"PeopleOps: {model_tag} x {prompt_tag}",
                        run_name=run_name
                    ) if hasattr(self._langfuse, "_create_experiment_run_name") else run_name
                    exp_res = await self._langfuse._run_experiment_async(
                        name=f"PeopleOps: {model_tag} x {prompt_tag}",
                        run_name=formatted_name,
                        description=f"Evaluation of {active_model} on {target_prompt_name} (v{target_prompt_ver or 'live'})",
                        data=items_to_run,
                        task=eval_task,
                        evaluators=evaluators,
                        composite_evaluator=None,
                        run_evaluators=run_evaluators,
                        max_concurrency=1,
                        metadata=exp_metadata
                    )
                else:
                    # Public API is synchronous (it drives its own event loop), so keep it off ours.
                    exp_res = await asyncio.to_thread(
                        self._langfuse.run_experiment,
                        name=f"PeopleOps: {model_tag} x {prompt_tag}",
                        run_name=run_name,
                        description=f"Evaluation of {active_model} on {target_prompt_name} (v{target_prompt_ver or 'live'})",
                        data=items_to_run,
                        task=eval_task,
                        evaluators=evaluators,
                        run_evaluators=run_evaluators,
                        max_concurrency=1,
                        metadata=exp_metadata,
                    )
                dataset_run_url = getattr(exp_res, "dataset_run_url", None)
                dataset_run_id = getattr(exp_res, "dataset_run_id", getattr(exp_res, "experiment_id", None))

                for r in getattr(exp_res, "item_results", []):
                    item_input = getattr(r, "item", {}).get("input") if isinstance(getattr(r, "item", None), dict) else getattr(getattr(r, "item", None), "input", {})
                    prompt_str = item_input.get("prompt", "") if isinstance(item_input, dict) else str(item_input)
                    out = getattr(r, "output", {}) or {}
                    resp_str = out.get("response", "") if isinstance(out, dict) else str(out)
                    evals_dict = {getattr(e, "name", str(i)): getattr(e, "value", 0.0) for i, e in enumerate(getattr(r, "evaluations", []))}
                    ov_score = evals_dict.get("overall_quality", 0.0)
                    sf_score = evals_dict.get("safety_and_pii_zero_leakage", 1.0)
                    is_passed = (ov_score >= 0.70 and sf_score >= 0.80)

                    if is_passed:
                        passed_count += 1
                    total_score_sum += ov_score

                    results.append({
                        "prompt": prompt_str,
                        "response_preview": resp_str[:120].replace("\n", " "),
                        "agent_routed": out.get("agent_routed", "HR_ROOT_ORCHESTRATOR"),
                        "latency_ms": out.get("latency_ms", 0.0),
                        "cost_usd": out.get("cost_usd", 0.0) or 0.0,
                        "evaluations": evals_dict,
                        "overall_score": ov_score,
                        "passed": is_passed
                    })

                self._langfuse.flush()
            except Exception as e:
                logger.warning(f"Notice: Native run_experiment encountered error ({e}), executing fallback: {e}")

        # Fallback if native execution failed
        if not results:
            for item in items_to_run:
                inp = getattr(item, "input", None) or (item.get("input") if isinstance(item, dict) else item)
                prompt = inp.get("prompt", str(inp)) if isinstance(inp, dict) else str(inp)
                t0 = time.perf_counter()
                fallback_session = eval_session_id("fallback")
                try:
                    chat_res = await llm_root_orchestrator.process_message(
                        db=db_session,
                        user=test_user,
                        message=prompt,
                        session_id=fallback_session
                    )
                    await discard_eval_session(fallback_session)
                    duration_ms = (time.perf_counter() - t0) * 1000
                    resp_text = chat_res.response
                    judge_res = llm_judge_service.evaluate_response(
                        query=prompt,
                        response_text=resp_text,
                        expected_keywords=inp.get("must_contain_keywords", []),
                        forbidden_terms=inp.get("forbidden_terms", []),
                        statutory_clause=inp.get("statutory_clause"),
                        latency_ms=duration_ms,
                        push_to_langfuse=False  # no active trace here, so there is nothing to attach scores to
                    )
                    if judge_res.passed:
                        passed_count += 1
                    total_score_sum += judge_res.overall_score
                    results.append({
                        "prompt": prompt,
                        "response_preview": resp_text[:120].replace("\n", " "),
                        "agent_routed": chat_res.agent_routed,
                        "latency_ms": round(duration_ms, 1),
                        "cost_usd": getattr(chat_res, "cost_usd", 0.0) or 0.0,
                        "evaluations": judge_res.metrics,
                        "overall_score": judge_res.overall_score,
                        "passed": judge_res.passed
                    })
                except Exception as ex:
                    duration_ms = (time.perf_counter() - t0) * 1000
                    results.append({
                        "prompt": prompt,
                        "error": str(ex),
                        "passed": False,
                        "overall_score": 0.0,
                        "latency_ms": round(duration_ms, 1)
                    })

        total_duration = round(time.time() - start_time_all, 2)
        total_cases = len(items_to_run)
        avg_score = round(total_score_sum / max(1, total_cases), 3)
        pass_rate = round((passed_count / max(1, total_cases)) * 100, 1)

        return {
            "run_id": run_id,
            "run_name": run_name,
            "dataset_name": DATASET_NAME,
            "dataset_run_id": dataset_run_id,
            "dataset_run_url": dataset_run_url,
            "total_cases": total_cases,
            "passed_cases": passed_count,
            "failed_cases": total_cases - passed_count,
            "pass_rate_percent": pass_rate,
            "average_overall_score": avg_score,
            "total_duration_sec": total_duration,
            "model": active_model,
            "prompt_name": target_prompt_name,
            "prompt_version": target_prompt_ver,
            "prompt_label": target_prompt_lbl,
            "prompt_text": effective_prompt_text,
            "judge": llm_judge_service.judge_model or "heuristic",
            "total_cost_usd": round(sum(r.get("cost_usd", 0.0) or 0.0 for r in results), 6),
            "average_latency_ms": round(sum(r.get("latency_ms", 0.0) or 0.0 for r in results) / max(1, total_cases), 1),
            "evaluators": [
                "policy_groundedness",
                "safety_and_pii_zero_leakage",
                "helpfulness_and_clarity",
                "statutory_compliance",
                "latency_sla",
                "overall_quality"
            ],
            "results": results
        }

    async def run_comparison_experiment(
        self,
        baseline: Optional[Dict[str, Any]] = None,
        challenger: Optional[Dict[str, Any]] = None,
        limit: int = 3,
        test_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs an automated A/B comparison experiment in Langfuse:
        - Baseline: Config A (e.g. current production prompt + gpt-oss-120b)
        - Challenger: Config B (e.g. prompt v2 / candidate prompt + gemini-2.5-flash)
        Returns results for both runs with comparison delta and direct Langfuse comparison links.
        """
        b_cfg = baseline or {
            "model_name": "groq/openai/gpt-oss-120b",
            "prompt_name": "peopleops-root-orchestrator",
            "prompt_version": 1,
            "run_name": f"baseline-gpt120b-prompt-v1-{int(time.time())}"
        }
        c_cfg = challenger or {
            "model_name": "gemini-3.8-flash",
            "prompt_name": "peopleops-root-orchestrator",
            "prompt_version": 13,
            "run_name": f"challenger-gemini-prompt-v13-{int(time.time())}"
        }

        logger.info(f"[Comparison-Experiment] 1/2: Executing Baseline ({b_cfg.get('run_name')})...")
        res_baseline = await self.run_golden_benchmark_experiment(
            experiment_run_name=b_cfg.get("run_name"),
            limit=limit,
            model_name=b_cfg.get("model_name"),
            prompt_name=b_cfg.get("prompt_name"),
            prompt_version=b_cfg.get("prompt_version"),
            prompt_label=b_cfg.get("prompt_label"),
            test_id=test_id
        )

        logger.info(f"[Comparison-Experiment] 2/2: Executing Challenger ({c_cfg.get('run_name')})...")
        res_challenger = await self.run_golden_benchmark_experiment(
            experiment_run_name=c_cfg.get("run_name"),
            limit=limit,
            model_name=c_cfg.get("model_name"),
            prompt_name=c_cfg.get("prompt_name"),
            prompt_version=c_cfg.get("prompt_version"),
            prompt_label=c_cfg.get("prompt_label"),
            test_id=test_id
        )

        score_diff = round(res_challenger["average_overall_score"] - res_baseline["average_overall_score"], 3)
        pass_rate_diff = round(res_challenger["pass_rate_percent"] - res_baseline["pass_rate_percent"], 1)

        return {
            "status": "comparison_complete",
            "baseline": {
                "run_name": res_baseline["run_name"],
                "url": res_baseline["dataset_run_url"],
                "model": b_cfg.get("model_name"),
                "prompt": f"{b_cfg.get('prompt_name')}:v{b_cfg.get('prompt_version', 'live')}",
                "pass_rate": f"{res_baseline['pass_rate_percent']}%",
                "avg_score": res_baseline["average_overall_score"],
                "duration_sec": res_baseline["total_duration_sec"]
            },
            "challenger": {
                "run_name": res_challenger["run_name"],
                "url": res_challenger["dataset_run_url"],
                "model": c_cfg.get("model_name"),
                "prompt": f"{c_cfg.get('prompt_name')}:v{c_cfg.get('prompt_version', 'live')}",
                "pass_rate": f"{res_challenger['pass_rate_percent']}%",
                "avg_score": res_challenger["average_overall_score"],
                "duration_sec": res_challenger["total_duration_sec"]
            },
            "comparison_summary": {
                "score_delta": score_diff,
                "pass_rate_delta": f"{pass_rate_diff:+}%",
                "winner": (
                    "Challenger" if score_diff > 0
                    else "Baseline" if score_diff < 0
                    else "Tie"
                ),
                "langfuse_experiments_url": f"{settings.LANGFUSE_BASE_URL or 'https://cloud.langfuse.com'}/project/{settings.LANGFUSE_PUBLIC_KEY}/datasets/peopleops-golden-benchmark-25"
            }
        }

    # ── Grid testing: prompt versions x models ─────────────────────────────────

    @staticmethod
    def _variant_tag(variant: Dict[str, Any]) -> str:
        return f"v{variant['version']}" if "version" in variant else str(variant["label"])

    async def run_grid_experiment(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Runs every (prompt variant x model) cell as its own Langfuse experiment run, then ranks them.

        `body` is a grid config (see `app.evaluations.grid_config`); invalid configs raise GridConfigError
        before anything runs. A failing cell is recorded and the grid continues. With `optimization.enabled`,
        the best cell's prompt is refined if it scores below the threshold (published under a non-live label).
        """
        from app.evaluations.grid_config import normalize_grid_config

        cfg = normalize_grid_config(body)
        started = time.time()
        stamp = int(started)

        cells: List[Dict[str, Any]] = []
        for variant in cfg["variants"]:
            for model in cfg["models"]:
                cells.append(await self._run_grid_cell(cfg, variant, model, stamp))

        scored = [c for c in cells if c["status"] == "ok"]
        best = max(scored, key=lambda c: (c["average_score"], c["pass_rate_percent"]), default=None)

        matrix: Dict[str, Dict[str, Optional[float]]] = {}
        for cell in cells:
            matrix.setdefault(cell["prompt"], {})[cell["model"]] = cell.get("average_score")

        optimization = None
        if cfg["optimization"]:
            optimization = (
                await self._optimize_best_cell(cfg, best)
                if best else {"ran": False, "reason": "no successful grid cell to optimise"}
            )

        public_cells = [{k: v for k, v in c.items() if not k.startswith("_")} for c in cells]
        warnings = []
        if settings.MOCK_LLM_ENABLED:
            warnings.append(
                "MOCK_LLM_ENABLED=true: every cell ran on the mock provider, so model names and scores say nothing "
                "about the real models. Set MOCK_LLM_ENABLED=false for a meaningful grid."
            )
        return {
            "status": "grid_complete" if scored else "grid_failed",
            "mock_mode": bool(settings.MOCK_LLM_ENABLED),
            "warnings": warnings,
            "run_prefix": cfg["run_prefix"],
            "prompt_name": cfg["prompt_name"],
            "judge": cfg["judge"] or "heuristic",
            "cells_total": len(cells),
            "cells_succeeded": len(scored),
            "cells": public_cells,
            "matrix": matrix,
            "best": ({k: v for k, v in best.items() if not k.startswith("_")} if best else None),
            "optimization": optimization,
            "duration_sec": round(time.time() - started, 1),
            "langfuse_datasets_url": (
                f"{settings.LANGFUSE_BASE_URL or settings.LANGFUSE_HOST}/project/{settings.LANGFUSE_PUBLIC_KEY}/datasets"
                if settings.LANGFUSE_PUBLIC_KEY else None
            ),
        }

    async def run_grid_tracked(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """run_grid_experiment, recording progress/outcome in `last_grid_run` (used by background triggers)."""
        self.last_grid_run = {"status": "running", "started_at": time.time()}
        try:
            result = await self.run_grid_experiment(body)
        except Exception as exc:
            logger.exception("Grid run failed")
            self.last_grid_run = {"status": "error", "error": str(exc), "finished_at": time.time()}
            return self.last_grid_run
        self.last_grid_run = {**result, "finished_at": time.time()}
        return self.last_grid_run

    async def _run_grid_cell(self, cfg: Dict[str, Any], variant: Dict[str, Any], model: Optional[str], stamp: int) -> Dict[str, Any]:
        prompt_tag = self._variant_tag(variant)
        model_label = model or "default"
        run_name = f"{cfg['run_prefix']}-{model_label.split('/')[-1]}-{prompt_tag}-{stamp}"
        cell = {"prompt": prompt_tag, "model": model_label, "run_name": run_name}
        # Anything but the plain live prompt was asked for explicitly: never fall back to a different prompt.
        strict = "version" in variant or variant.get("label") != "live"
        try:
            res = await self.run_golden_benchmark_experiment(
                experiment_run_name=run_name,
                limit=cfg["limit"],
                model_name=model,
                prompt_name=cfg["prompt_name"],
                prompt_version=variant.get("version"),
                prompt_label=variant.get("label"),
                test_ids=cfg["items"] or None,
                strict_prompt=strict,
                judge_model=cfg["judge"],
            )
        except Exception as exc:
            logger.warning("Grid cell %s failed: %s", run_name, exc)
            return {**cell, "status": "error", "error": str(exc)}
        return {
            **cell,
            "status": "ok",
            "url": res.get("dataset_run_url"),
            "average_score": res["average_overall_score"],
            "pass_rate_percent": res["pass_rate_percent"],
            "average_latency_ms": res.get("average_latency_ms"),
            "total_cost_usd": res.get("total_cost_usd"),
            "total_cases": res["total_cases"],
            "judge": res.get("judge"),
            "items": [
                {k: r.get(k) for k in ("prompt", "overall_score", "passed", "agent_routed", "latency_ms", "cost_usd", "evaluations", "response_preview")}
                for r in res.get("results", [])
            ],
            "_model": res.get("model") or model,
            "_prompt_text": res.get("prompt_text"),
            "_results": res.get("results", []),
        }

    # ── Prompt optimisation (reflective, GEPA-style) ───────────────────────────

    async def _optimize_best_cell(self, cfg: Dict[str, Any], best: Dict[str, Any]) -> Dict[str, Any]:
        from app.evaluations.prompt_optimizer import ReflectivePromptOptimizer, EvalOutcome

        opt = cfg["optimization"]
        base = {"ran": False, "algorithm": "reflective prompt evolution (GEPA-style, single candidate)"}
        if cfg["prompt_name"] != "peopleops-root-orchestrator":
            return {**base, "reason": "optimisation currently supports only the root orchestrator prompt"}
        if not best.get("_prompt_text"):
            return {**base, "reason": "the best cell did not report its prompt text"}

        judge = opt["judge"]
        model = opt["model"] or best["_model"]
        optimizer_model = opt["optimizer_model"] or judge or model
        items = cfg["items"] or [tc.test_id for tc in GOLDEN_BENCHMARK_25[: (cfg["limit"] or len(GOLDEN_BENCHMARK_25))]]

        failing = sorted(
            (r for r in best["_results"] if r.get("overall_score", 1.0) < opt["threshold"]),
            key=lambda r: r.get("overall_score", 0.0),
        )
        seed = EvalOutcome(
            avg_score=best["average_score"],
            failures=[
                {"prompt": r.get("prompt"), "response": r.get("response_preview"),
                 "score": r.get("overall_score"), "metrics": r.get("evaluations")}
                for r in failing[:5]
            ],
            metric_calls=len(items),
        )

        async def evaluate(text: str) -> EvalOutcome:
            return await self._evaluate_prompt_text(
                text, model=model, test_ids=items, judge_model=judge, threshold=opt["threshold"]
            )

        async def reflect(prompt: str, failures: List[Dict[str, Any]]) -> Optional[str]:
            return await asyncio.to_thread(self._reflect_on_failures, optimizer_model, prompt, failures)

        optimizer = ReflectivePromptOptimizer(
            evaluate, reflect, threshold=opt["threshold"], budget=opt["budget"], max_metric_calls=opt["max_metric_calls"]
        )
        outcome = await optimizer.optimize(best["_prompt_text"], seed)

        published_version = None
        if outcome.improved:
            published_version = self._publish_optimized_prompt(
                cfg["prompt_name"], outcome.best_prompt, opt["output_label"],
                f"Grid optimisation '{cfg['run_prefix']}': {outcome.seed_score:.2f} -> {outcome.best_score:.2f} "
                f"(model={model}, judge={judge or 'heuristic'})",
            )
        return {
            **base,
            "ran": outcome.stopped_reason != "threshold_met" or bool(outcome.rounds),
            "stopped_reason": outcome.stopped_reason,
            "seed_cell": {"prompt": best["prompt"], "model": best["model"]},
            "seed_score": round(outcome.seed_score, 3),
            "best_score": round(outcome.best_score, 3),
            "improved": outcome.improved,
            "metric_calls": outcome.metric_calls,
            "max_metric_calls": opt["max_metric_calls"],
            "optimizer_model": optimizer_model,
            "rounds": outcome.rounds,
            "output_label": opt["output_label"],
            "published_prompt_version": published_version,
            "published": published_version is not None,
            "optimized_prompt": outcome.best_prompt if outcome.improved else None,
            "note": "Published under the output label only; promote to 'live' manually after review.",
        }

    async def _evaluate_prompt_text(
        self, prompt_text: str, *, model: Optional[str], test_ids: List[str], judge_model: Optional[str], threshold: float
    ):
        """Score a candidate root prompt on the given golden items (one metric call per item)."""
        from app.agents.orchestrator import llm_root_orchestrator
        from app.models.user import User, UserRole
        from app.core.llm_bridge import snapshot_model_state, restore_model_state, set_active_model
        from app.agents.adk_fleet import refresh_adk_fleet_models, set_root_instruction_override
        from app.evaluations.prompt_optimizer import EvalOutcome

        wanted = set(test_ids)
        cases = [tc for tc in GOLDEN_BENCHMARK_25 if tc.test_id in wanted]
        user = User(id="EMP-004", email=EVAL_USER_EMAIL, full_name="Aarav Sharma",
                    role=UserRole.EMPLOYEE, is_active=True)

        scores: List[float] = []
        failures: List[Dict[str, Any]] = []
        async with _experiment_lock:
            state = snapshot_model_state()
            llm_judge_service.judge_model = judge_model
            try:
                if model:
                    refresh_adk_fleet_models(set_active_model(model))
                set_root_instruction_override(prompt_text)
                for tc in cases:
                    t0 = time.perf_counter()
                    opt_session = eval_session_id(f"opt_{tc.test_id}")
                    try:
                        reply = await llm_root_orchestrator.process_message(
                            db=None, user=user, message=tc.prompt, session_id=opt_session,
                        )
                    finally:
                        await discard_eval_session(opt_session)
                    latency = (time.perf_counter() - t0) * 1000
                    judged = llm_judge_service.evaluate_response(
                        query=tc.prompt, response_text=reply.response,
                        expected_keywords=tc.must_contain_keywords, forbidden_terms=tc.forbidden_terms,
                        statutory_clause=tc.statutory_clause, latency_ms=latency,
                        push_to_langfuse=False, reference_answer=tc.reference_answer,
                    )
                    scores.append(judged.overall_score)
                    if judged.overall_score < threshold:
                        failures.append({
                            "prompt": tc.prompt, "response": reply.response[:240], "score": judged.overall_score,
                            "metrics": judged.metrics, "feedback": judged.feedback,
                        })
                    await asyncio.sleep(0.3)
            finally:
                llm_judge_service.judge_model = None
                restore_model_state(state)
                set_root_instruction_override(None)
                refresh_adk_fleet_models(None)

        return EvalOutcome(
            avg_score=round(sum(scores) / max(1, len(scores)), 3), failures=failures, metric_calls=len(cases)
        )

    def _reflect_on_failures(self, optimizer_model: str, prompt: str, failures: List[Dict[str, Any]]) -> Optional[str]:
        """Ask the optimiser model for an improved prompt given the current one and its failures."""
        if settings.MOCK_LLM_ENABLED:
            return None  # mock mode never reaches a live provider
        cases = "\n".join(
            f"- Question: {f.get('prompt')}\n  Answer: {str(f.get('response'))[:240]}\n"
            f"  Scores: {f.get('metrics')}\n  Judge feedback: {f.get('feedback') or ''}"
            for f in failures[:5]
        ) or "(no per-item failures were recorded; improve general accuracy and clarity)"
        messages = [
            {"role": "system", "content": (
                "You improve system prompts for an HR assistant used by Indian employees under the Maharashtra "
                "Shops and Establishments Act. Given the current prompt and cases it handled badly, rewrite the prompt "
                "so those cases would be answered correctly. Keep every {{placeholder}} exactly as written and keep all "
                "privacy, PII, safety and statutory rules. Return ONLY the full improved prompt text: no commentary, "
                "no code fences."
            )},
            {"role": "user", "content": f"CURRENT PROMPT:\n{prompt}\n\nFAILING CASES:\n{cases}"},
        ]
        text = llm_judge_service._complete(optimizer_model, messages).strip()
        if text.startswith("```"):
            text = text.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        return text or None

    def _publish_optimized_prompt(self, name: str, text: str, label: str, message: str) -> Optional[int]:
        """Create a new prompt version carrying only the (non-live) output label."""
        if not self._langfuse:
            return None
        try:
            created = self._langfuse.create_prompt(
                name=name, prompt=text, labels=[label], type="text", commit_message=message
            )
            self._langfuse.flush()
            return getattr(created, "version", None)
        except Exception as exc:
            logger.warning("Could not publish optimised prompt '%s' as label '%s': %s", name, label, exc)
            return None


langfuse_dataset_service = LangfuseDatasetSyncService()
