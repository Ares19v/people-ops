"""Leave-policy numbers, read from data/company_policy_2026.json (the single source of truth).

Agents, mock providers and the knowledge graph used to carry their own copies of
"EL 18 / CL 8 / SL 12 ..." and drifted apart. Import from here instead.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_POLICY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
    "company_policy_2026.json",
)


@lru_cache(maxsize=1)
def _leave_policies() -> Dict[str, Dict[str, Any]]:
    try:
        with open(_POLICY_FILE, "r", encoding="utf-8") as fh:
            document = json.load(fh)
    except (OSError, ValueError) as exc:
        logger.error("Could not load company policy file %s: %s", _POLICY_FILE, exc)
        return {}
    return {
        p["leave_type"]: p
        for p in document.get("policies", [])
        if isinstance(p, dict) and p.get("leave_type")
    }


def _number(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def quota(leave_type: str) -> Optional[float]:
    """Annual entitlement in days (None if the policy has no numeric quota, e.g. LWP)."""
    return _number(_leave_policies().get(leave_type, {}).get("annual_quota"))


def max_accumulation(leave_type: str) -> Optional[float]:
    """Maximum days that can be accumulated / carried forward."""
    return _number(_leave_policies().get(leave_type, {}).get("max_accumulation"))


def days(value: Optional[float]) -> str:
    """Format a day count without a trailing '.0' (18.0 -> '18'); unknown -> 'n/a'."""
    if value is None:
        return "n/a"
    return str(int(value)) if float(value).is_integer() else str(value)
