"""Parsing and validation of grid-test configuration (prompt versions x models).

Accepted shapes (flat, or wrapped in "config" / "payload" as a Langfuse remote-experiment trigger may do):

    {"config": {
        "prompt_label": "baseline",            # a prompt label to test (default "live")
        "prompt_versions": ["v1", "v2", "v3"], # and/or explicit versions
        "models": ["openai/gpt-4o-mini", "gemini-2.0-flash"],
        "items": ["BENCH-01-LEAVE-BALANCES"],  # golden test ids (default: all, or `limit`)
        "judge": "openai/gpt-4o-mini",         # LLM judge model (default: keyword heuristics)
        "run_prefix": "clinical-gepa-openai",
        "optimization": {"enabled": true, "threshold": 0.8, "budget": "light", "max_metric_calls": 10,
                         "optimizer_model": "gemini-2.0-flash", "output_label": "gepa-v1"}
    }}
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app.evaluations.golden_dataset_25 import GOLDEN_BENCHMARK_25
from app.evaluations.prompt_optimizer import BUDGET_ROUNDS, PROTECTED_LABELS

DEFAULT_PROMPT = "peopleops-root-orchestrator"
MAX_GRID_CELLS = 12
GRID_KEYS = {"models", "prompt_versions", "prompt_labels", "items", "optimization", "judge", "run_prefix"}
_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]{1,60}$")
_VERSION = re.compile(r"^v?(\d+)$", re.I)


class GridConfigError(ValueError):
    """Raised with every problem found in a grid configuration."""

    def __init__(self, problems: List[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def normalize_trigger_body(body: Any) -> Dict[str, Any]:
    """Unwrap what Langfuse's remote-experiment trigger really sends.

    Observed delivery: {"projectId", "datasetId", "datasetName", "payload": "<default config as a JSON string>"}.
    The decoded payload is merged into the top level, so both {"config": {...}} and flat keys such as
    {"limit": 5} work, while the envelope fields (datasetName, ...) stay available.
    """
    if not isinstance(body, dict):
        return {}
    raw = body.get("payload")
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except ValueError:
            return body
        if isinstance(decoded, dict):
            envelope = {k: v for k, v in body.items() if k != "payload"}
            return {**envelope, **decoded}
    return body


def extract_config(body: Dict[str, Any]) -> Dict[str, Any]:
    """Find the config dict inside a trigger body ({"config": {...}}, {"payload": {...}} or flat)."""
    if not isinstance(body, dict):
        return {}
    for key in ("config", "payload"):
        inner = body.get(key)
        if isinstance(inner, dict):
            return inner["config"] if isinstance(inner.get("config"), dict) else inner
    return body


def is_grid_request(body: Dict[str, Any]) -> bool:
    body = normalize_trigger_body(body)
    if not isinstance(body, dict):
        return False
    if isinstance(body.get("config"), dict):
        return True
    return bool(GRID_KEYS & set(extract_config(body)))


def _as_list(value: Any) -> List[Any]:
    if value is None or value == "":
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _parse_optimization(raw: Any, default_judge: Optional[str], problems: List[str]) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict) or not raw.get("enabled", False):
        return None
    threshold = raw.get("threshold", 0.8)
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not 0 < float(threshold) <= 1:
        problems.append("optimization.threshold must be a number in (0, 1]")
        threshold = 0.8
    budget = str(raw.get("budget", "light")).lower()
    if budget not in BUDGET_ROUNDS:
        problems.append(f"optimization.budget must be one of {sorted(BUDGET_ROUNDS)}")
    max_calls = raw.get("max_metric_calls", 10)
    if isinstance(max_calls, bool) or not isinstance(max_calls, int) or max_calls < 1:
        problems.append("optimization.max_metric_calls must be a positive integer")
        max_calls = 10
    output_label = str(raw.get("output_label") or "optimized")
    if not _SAFE_NAME.match(output_label) or output_label.lower() in PROTECTED_LABELS:
        problems.append(
            f"optimization.output_label must be 1-60 chars of [A-Za-z0-9._-] and cannot be one of {sorted(PROTECTED_LABELS)} "
            "(optimised prompts are never published as live)"
        )
    return {
        "threshold": float(threshold),
        "budget": budget if budget in BUDGET_ROUNDS else "light",
        "max_metric_calls": max_calls,
        "model": raw.get("model") or None,
        "optimizer_model": raw.get("optimizer_model") or None,
        "judge": raw.get("judge") or default_judge,
        "output_label": output_label,
    }


def normalize_grid_config(body: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a grid request and return a normalised config. Raises GridConfigError listing all problems."""
    cfg = extract_config(normalize_trigger_body(body))
    problems: List[str] = []

    prompt_name = str(cfg.get("prompt_name") or DEFAULT_PROMPT)

    variants: List[Dict[str, Any]] = []
    labels = [str(l) for l in _as_list(cfg.get("prompt_labels"))]
    if cfg.get("prompt_label"):
        labels.insert(0, str(cfg["prompt_label"]))
    for label in labels:
        variants.append({"label": label})
    for raw_version in _as_list(cfg.get("prompt_versions")):
        match = _VERSION.match(str(raw_version).strip())
        if not match:
            problems.append(f"prompt_versions entry '{raw_version}' is not a version like 3 or 'v3'")
            continue
        variants.append({"version": int(match.group(1))})
    if not variants:
        variants = [{"label": "live"}]
    seen, unique_variants = set(), []
    for variant in variants:
        key = tuple(sorted(variant.items()))
        if key not in seen:
            seen.add(key)
            unique_variants.append(variant)

    models = [str(m).strip() for m in _as_list(cfg.get("models")) if str(m).strip()] or [None]
    models = list(dict.fromkeys(models))

    known_ids = {tc.test_id for tc in GOLDEN_BENCHMARK_25}
    items = [str(i) for i in _as_list(cfg.get("items"))]
    unknown = [i for i in items if i not in known_ids]
    if unknown:
        problems.append(f"unknown items {unknown}; use golden test ids such as 'BENCH-01-LEAVE-BALANCES'")

    limit = cfg.get("limit")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
        problems.append("limit must be a positive integer")
        limit = None

    run_prefix = str(cfg.get("run_prefix") or "grid")
    if not _SAFE_NAME.match(run_prefix):
        problems.append("run_prefix must be 1-60 chars of [A-Za-z0-9._-]")

    judge = str(cfg["judge"]).strip() if cfg.get("judge") else None
    optimization = _parse_optimization(cfg.get("optimization"), judge, problems)

    cell_count = len(unique_variants) * len(models)
    if cell_count > MAX_GRID_CELLS:
        problems.append(f"grid has {cell_count} cells ({len(unique_variants)} prompts x {len(models)} models); the maximum is {MAX_GRID_CELLS}")

    if problems:
        raise GridConfigError(problems)

    return {
        "prompt_name": prompt_name,
        "variants": unique_variants,
        "models": models,
        "items": items,
        "limit": limit,
        "run_prefix": run_prefix,
        "judge": judge,
        "optimization": optimization,
    }
