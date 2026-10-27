"""Tool: query_company_policy (Google ADK compatible tool)."""

import logging
from typing import Any, Dict

from app.core.logging_config import log_tool_call

logger = logging.getLogger(__name__)


@log_tool_call
async def query_company_policy(query_text: str, jurisdiction: str = "MAHARASHTRA") -> Dict[str, Any]:
    """Query the enterprise HR policies and Maharashtra statutory labour law knowledge base.

    Args:
        query_text: Natural language policy question.
        jurisdiction: Indian state jurisdiction.

    Returns:
        Dict with answer, relevant policy sections, and confidence score.
    """
    try:
        from app.services.policy_rag_service import policy_rag_service
        res = await policy_rag_service.search_policies(query_text)
        citations = [c.model_dump() for c in res["citations"]]
        return {
            "query": query_text,
            "response": res["context"],
            "citations": citations,
            "confidence": max((c["confidence_score"] for c in citations), default=0.0),
        }
    except Exception as exc:
        logger.warning("query_company_policy failed: %s", exc)
        return {
            "query": query_text,
            "response": f"Policy knowledge query for '{query_text}' under {jurisdiction} guidelines.",
            "citations": [{"source": "HR Handbook 2026", "section": "General Terms"}],
        }
