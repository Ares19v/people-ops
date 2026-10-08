"""Tool: get_occupational_health_guidelines (Google ADK compatible tool)."""

import logging
from typing import Any, Dict

from app.core.logging_config import log_tool_call

logger = logging.getLogger(__name__)


@log_tool_call
async def get_occupational_health_guidelines(condition_or_symptom: str) -> Dict[str, Any]:
    """Retrieve occupational health guidance and statutory sick leave certification rules.

    Args:
        condition_or_symptom: Reported medical symptom or inquiry.

    Returns:
        Dict with occupational health protocol, certificate requirements, and triage guidance.
    """
    try:
        requires_cert = any(
            w in condition_or_symptom.lower()
            for w in ["hospital", "surgery", "fever", "fracture", "accident"]
        )
        return {
            "condition": condition_or_symptom,
            "requires_doctor_certificate": requires_cert,
            "protocol": (
                "For medical absence exceeding 2 consecutive days, a registered medical practitioner's certificate is required per ESI Act and company health policy."
                if requires_cert
                else "Single-day sick leaves can be self-certified upon resumption of work."
            ),
            "doctor_consultation_available": True,
            "telehealth_hotline": "+91-800-INTELERA-CARE",
        }
    except Exception as exc:
        return {"error": f"Health guideline lookup failed: {str(exc)}"}
