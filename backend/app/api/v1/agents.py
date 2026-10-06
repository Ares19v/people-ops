from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.services.auth_service import get_current_user
from app.agents.orchestrator import orchestrator
from app.agents.langgraph_orchestrator import enterprise_agent_graph
from app.compliance.phi_engine import compliance_engine
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class RedactPayload(BaseModel):
    text: str
    session_id: Optional[str] = None

class DeRedactPayload(BaseModel):
    text: str
    session_id: str

router = APIRouter(prefix="/agents", tags=["Multi-Agent System"])

@router.post("/chat", response_model=AgentChatResponse)
async def chat_with_multi_agent_system(
    payload: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    response = await orchestrator.process_message(
        db=db,
        user=current_user,
        message=payload.message,
        session_id=payload.session_id,
        target_agent=payload.target_agent
    )
    return response

@router.post("/langgraph-chat")
async def chat_with_langgraph(
    payload: AgentChatRequest,
    current_user: User = Depends(get_current_user)
):
    session_id = payload.session_id or f"sess_{current_user.id[:8]}"
    initial_state = {
        "session_id": session_id,
        "user_id": current_user.id,
        "user_role": current_user.role.value,
        "raw_input": payload.message,
        "redacted_input": "",
        "phi_detected_count": 0,
        "guardrail_status": "",
        "guardrail_tripped": None,
        "routed_agent": payload.target_agent or "",
        "agent_output": "",
        "citations": [],
        "structured_action": None,
        "requires_hitl_approval": False,
        "is_approved": False,
        "final_response": "",
        "duration_ms": 0.0,
    }

    result = enterprise_agent_graph.invoke(initial_state)
    return {
        "session_id": session_id,
        "response": result.get("final_response"),
        "agent_routed": result.get("routed_agent"),
        "guardrail_status": result.get("guardrail_status"),
        "guardrail_tripped": result.get("guardrail_tripped"),
        "phi_detected_count": result.get("phi_detected_count"),
        "requires_hitl_approval": result.get("requires_hitl_approval"),
        "citations": result.get("citations"),
    }

@router.post("/compliance/redact")
async def compliance_redact(
    payload: RedactPayload,
    current_user: User = Depends(get_current_user)
):
    session_id = payload.session_id or f"sess_{current_user.id[:8]}"
    res = compliance_engine.redact(payload.text, session_id=session_id)
    return {
        "session_id": session_id,
        "redacted_text": res.redacted_text,
        "entities_count": len(res.entities_detected),
        "tokens": res.tokens_created
    }

@router.post("/compliance/de-redact")
async def compliance_deredact(
    payload: DeRedactPayload,
    current_user: User = Depends(get_current_user)
):
    restored = compliance_engine.de_redact(payload.text, session_id=payload.session_id, user_role=current_user.role.value)
    return {
        "session_id": payload.session_id,
        "user_role": current_user.role.value,
        "restored_text": restored
    }
