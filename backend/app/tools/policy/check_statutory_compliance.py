"""Tool: check_statutory_compliance (Google ADK compatible tool)."""

import logging
from typing import Any, Dict, Optional

from app.core.logging_config import log_tool_call

logger = logging.getLogger(__name__)


@log_tool_call
async def check_statutory_compliance(
    jurisdiction: str,
    hours_worked: float = 0.0,
    leave_type: Optional[str] = None,
    consecutive_days: float = 0.0,
) -> Dict[str, Any]:
    """Check actions against Indian state statutory mandates (Maharashtra 2017, Karnataka 1961, Delhi 1954).

    Args:
        jurisdiction: Indian state ("MAHARASHTRA", "KARNATAKA", "DELHI").
        hours_worked: Total daily hours to test for overtime violations (>9h or >11h cap).
        leave_type: Leave type code if testing leave validity.
        consecutive_days: Duration of continuous leave requested.

    Returns:
        Dict detailing compliance status and citations under state acts.
    """
    try:
        jur = jurisdiction.upper()
        violations = []

        if hours_worked > 11.0:
            violations.append(
                f"Statutory Daily Cap Exceeded: Max total working hours under {jur} Shops & Establishments Act is 11 hours (worked {hours_worked}h)."
            )
        elif hours_worked > 9.0:
            violations.append(
                f"Overtime Incurred: Work exceeding 9 hours/day triggers statutory overtime compensation at double rate (2.0x)."
            )

        if leave_type == "CL" and consecutive_days > 3.0:
            violations.append(
                f"Casual Leave Limit: Under {jur} rules, Casual Leave cannot be taken for more than 3 consecutive days."
            )

        is_valid = len(violations) == 0 or (len(violations) == 1 and "Overtime Incurred" in violations[0])

        return {
            "jurisdiction": jur,
            "is_valid": is_valid,
            "findings": violations if violations else ["Action complies with statutory parameters."],
            "status": "APPROVED" if is_valid else "VIOLATION_DETECTED",
        }
    except Exception as exc:
        return {"error": f"Statutory evaluation failed: {str(exc)}"}
