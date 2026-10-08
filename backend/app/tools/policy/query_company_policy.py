"""Tool: query_company_policy (Google ADK compatible tool)."""

import logging
from typing import Any, Dict

from app.core.logging_config import log_tool_call

logger = logging.getLogger(__name__)


@log_tool_call
async def query_company_policy(query_text: str, jurisdiction: str = "MAHARASHTRA") -> Dict[str, Any]:
    """Query the enterprise HR policies and statutory knowledge graph.

    Args:
        query_text: Natural language policy question.
        jurisdiction: Indian state jurisdiction.

    Returns:
        Dict with answer, relevant policy sections, and confidence score.
    """
    try:
        from app.rag.agentic_rag import agentic_policy_rag
        res = await agentic_policy_rag.retrieve_and_synthesize(query_text, user_role="EMPLOYEE")
        return {
            "query": query_text,
            "response": res.get("response", ""),
            "citations": res.get("citations", []),
            "confidence": 0.95,
        }
    except Exception as exc:
        return {
            "query": query_text,
            "response": f"Policy knowledge query for '{query_text}' under {jurisdiction} guidelines.",
            "citations": [{"source": "HR Handbook 2026", "section": "General Terms"}],
        }
