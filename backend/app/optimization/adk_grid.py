"""Prompt-version x model grid on Google ADK's own evaluators.

ADK has no native "run this eval for prompt v1, v2 and models A, B". This module is the trigger: for every cell it
sets the root orchestrator prompt (a Langfuse version/label, or literal text) and the model for the whole fleet, runs
the golden cases through ADK's LocalEvalService against the isolated SQLite database, and ranks the cells.

It accepts the same config as the Langfuse grid (`app.evaluations.grid_config`), plus `prompt_texts`:

    {"config": {"prompt_versions": ["v1", "v2"], "models": ["openai/gpt-4o-mini", "groq/openai/gpt-oss-120b"],
                "items": ["BENCH-01-LEAVE-BALANCES"], "judge": "openai/gpt-4o-mini", "run_prefix": "adk-grid",
                "prompt_texts": {"poor-seed": "You are an HR bot."}}}

Cells run one after another because the model and prompt are process-wide settings of the agent fleet.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from app.evaluations.adk_expectations import adk_cases, to_eval_set
from app.evaluations.adk_support import AdkCaseResult, run_adk_evaluation
from app.evaluations.grid_config import DEFAULT_PROMPT, MAX_GRID_CELLS, GridConfigError, extract_config, normalize_grid_config, normalize_trigger_body
from app.optimization.metric import composite, eval_config_for
from app.optimization.runtime import to_adk_instruction

logger = logging.getLogger(__name__)

PROMPT_TEXTS_KEY = "prompt_texts"
PASS_COMPOSITE = 0.8


def split_prompt_texts(body: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, str]]:
    """Take `prompt_texts` out of the request (the Langfuse grid parser does not know the key)."""
    cfg = extract_config(normalize_trigger_body(body))
    texts = {str(k): str(v) for k, v in (cfg.get(PROMPT_TEXTS_KEY) or {}).items() if str(v).strip()}
    clean = {k: v for k, v in cfg.items() if k != PROMPT_TEXTS_KEY}
    return clean, texts


def default_item_ids(*, deterministic_only: bool, include_mutating: bool) -> List[str]:
    """Cases that are safe to repeat across cells: mutating ones (apply leave, sync) change the database."""
    ids = [c.test_id for c in adk_cases(include_mutating=include_mutating)]
    if deterministic_only:
        from app.evaluations.adk_expectations import EXPECTATIONS

        ids = [i for i in ids if EXPECTATIONS[i].deterministic]
    return ids


def resolve_prompt_text(prompt_name: str, variant: Dict[str, Any]) -> tuple[str, Optional[int]]:
    """The prompt text for a variant. Never falls back to another prompt: a missing version is an error."""
    from app.observability.langfuse_client import get_langfuse

    client = get_langfuse()
    if client is None:
        raise RuntimeError("Prompt versions and labels are resolved through Langfuse, which is not connected.")
    if "version" in variant:
        prompt = client.get_prompt(prompt_name, version=variant["version"])
    else:
        prompt = client.get_prompt(prompt_name, label=variant["label"])
    return prompt.prompt, getattr(prompt, "version", variant.get("version"))


def _aggregate(results: List[AdkCaseResult]) -> Dict[str, Any]:
    scored = [(r, composite(r)) for r in results]
    values = [s for _, s in scored if s is not None]
    per_metric: Dict[str, List[float]] = {}
    for result in results:
        for name, entry in result.metrics.items():
            if entry.get("score") is not None:
                per_metric.setdefault(name, []).append(float(entry["score"]))
    latencies = [r.latency_ms for r in results if r.latency_ms]
    return {
        "composite": round(sum(values) / len(values), 3) if values else None,
        "scored_cases": len(values),
        "errored_cases": sum(1 for _, s in scored if s is None),
        # Share of cases whose composite is at least PASS_COMPOSITE. ADK's own status (every enabled metric must pass,
        # including the weak ROUGE check) is kept separately.
        "pass_rate_percent": round(100 * sum(1 for v in values if v >= PASS_COMPOSITE) / len(values), 1) if values else 0.0,
        "adk_strict_pass_rate_percent": round(100 * sum(1 for r in results if r.passed) / len(results), 1) if results else 0.0,
        "metrics": {name: round(sum(v) / len(v), 3) for name, v in per_metric.items()},
        "average_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
    }


async def run_adk_grid(
    body: Dict[str, Any],
    *,
    root_agent: Any,
    evalset: str = "deterministic",
    metrics: str = "standard",
    include_mutating: bool = False,
) -> Dict[str, Any]:
    """Run every (prompt variant x model) cell through ADK's evaluators and rank them."""
    from app.core.config import settings
    from app.core.llm_bridge import restore_model_state, set_active_model, snapshot_model_state
    from app.agents.adk_fleet import refresh_adk_fleet_models, set_root_instruction_override

    clean, literal_texts = split_prompt_texts(body)
    cfg = normalize_grid_config(clean)
    if cfg["prompt_name"] != DEFAULT_PROMPT:
        raise GridConfigError([f"the ADK grid varies the root prompt only; use prompt_name '{DEFAULT_PROMPT}'"])
    cells_wanted = (len(cfg["variants"]) + len(literal_texts)) * len(cfg["models"])
    if cells_wanted > MAX_GRID_CELLS:
        raise GridConfigError([f"grid has {cells_wanted} cells; the maximum is {MAX_GRID_CELLS}"])

    allowed = default_item_ids(deterministic_only=(evalset == "deterministic"), include_mutating=include_mutating)
    items = cfg["items"] or allowed
    if cfg["limit"]:
        items = items[: cfg["limit"]]
    eval_set = to_eval_set(eval_set_id=f"adk_grid_{evalset}", test_ids=items)
    eval_config = eval_config_for(metrics, cfg["judge"])

    variants: List[Dict[str, Any]] = [dict(v) for v in cfg["variants"]] + [{"text": t, "tag": tag} for tag, t in literal_texts.items()]
    started = time.time()
    stamp = int(started)
    state = snapshot_model_state()
    cells: List[Dict[str, Any]] = []
    try:
        for variant in variants:
            tag = variant.get("tag") or (f"v{variant['version']}" if "version" in variant else str(variant["label"]))
            for model in cfg["models"]:
                model_label = model or "default"
                cell: Dict[str, Any] = {"prompt": tag, "model": model_label, "run_name": f"{cfg['run_prefix']}-{model_label.split('/')[-1]}-{tag}-{stamp}"}
                try:
                    raw = variant["text"] if "text" in variant else resolve_prompt_text(cfg["prompt_name"], variant)[0]
                    text = to_adk_instruction(raw)
                    refresh_adk_fleet_models(set_active_model(model))
                    set_root_instruction_override(text)
                    results = await run_adk_evaluation(eval_set, eval_config, root_agent=root_agent, test_ids=items)
                except Exception as exc:
                    logger.warning("ADK grid cell %s failed: %s", cell["run_name"], exc)
                    cells.append({**cell, "status": "error", "error": str(exc)[:300]})
                    continue
                aggregate = _aggregate(results)
                cells.append({
                    **cell,
                    "status": "ok" if aggregate["composite"] is not None else "error",
                    **aggregate,
                    "prompt_chars": len(text),
                    "cases": [
                        {"id": r.test_id, "score": composite(r), "status": r.status, "tools": [c["tool_name"] for c in r.actual_tool_use],
                         "expected_tools": [c["tool_name"] for c in r.expected_tool_use], "error": r.error}
                        for r in results
                    ],
                })
    finally:
        restore_model_state(state)
        set_root_instruction_override(None)
        refresh_adk_fleet_models(None)

    ok = [c for c in cells if c["status"] == "ok"]
    best = max(ok, key=lambda c: (c["composite"], c["pass_rate_percent"]), default=None)
    matrix: Dict[str, Dict[str, Optional[float]]] = {}
    for cell in cells:
        matrix.setdefault(cell["prompt"], {})[cell["model"]] = cell.get("composite")
    warnings = []
    if settings.MOCK_LLM_ENABLED:
        warnings.append("MOCK_LLM_ENABLED=true: every cell ran on the mock provider; scores say nothing about the real models.")
    if include_mutating:
        warnings.append("Mutating cases were included: they change the isolated database, so later cells start from a different state.")
    return {
        "status": "grid_complete" if ok else "grid_failed",
        "engine": "google-adk",
        "evalset": evalset,
        "metrics_preset": metrics,
        "judge": cfg["judge"] or "default",
        "run_prefix": cfg["run_prefix"],
        "items": items,
        "cells_total": len(cells),
        "cells_succeeded": len(ok),
        "matrix": matrix,
        "best": best,
        "cells": cells,
        "warnings": warnings,
        "duration_sec": round(time.time() - started, 1),
    }
