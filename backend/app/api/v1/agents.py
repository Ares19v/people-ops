import asyncio
import json
import time
from fastapi import APIRouter, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User, UserRole
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.services.auth_service import get_current_user, require_role
from app.agents.orchestrator import orchestrator
from app.agents.langgraph_orchestrator import enterprise_agent_graph
from app.compliance.phi_engine import compliance_engine
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

from app.services.langfuse_prompt_service import langfuse_prompt_service
from app.agents.adk_fleet import sync_agent_instructions

class RedactPayload(BaseModel):
    text: str
    session_id: Optional[str] = None

class DeRedactPayload(BaseModel):
    text: str
    session_id: str

router = APIRouter(prefix="/agents", tags=["Multi-Agent System"])

@router.get("/prompts")
async def list_agent_prompts(
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN]))
):
    """Inspect all decoupled subagent prompts and their version/source (Restricted to HR/Admin)."""
    prompts_info = {}
    with langfuse_prompt_service._lock:
        for k, v in langfuse_prompt_service._cache.items():
            prompts_info[k] = {
                "name": v.name,
                "version": v.version,
                "label": v.label,
                "source": v.source,
                "template": v.template,
                "cached_at": v.fetched_at,
            }
    return {
        "status": "success",
        "langfuse_connected": langfuse_prompt_service._langfuse_client is not None,
        "prompts_count": len(prompts_info),
        "prompts": prompts_info,
    }

@router.post("/prompts/webhook")
async def langfuse_prompt_webhook(
    payload: Dict[str, Any],
    x_webhook_secret: Optional[str] = Header(None)
):
    """Authenticated webhook listener for Langfuse prompt updates or external CMS."""
    from app.core.config import settings
    expected_secret = getattr(settings, "WEBHOOK_SECRET", None) or "peopleops_webhook_secret_2026"
    if x_webhook_secret != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid or missing X-Webhook-Secret header."
        )

    res = langfuse_prompt_service.handle_webhook_event(payload)
    sync_agent_instructions()
    return res

@router.post("/prompts/reload")
async def reload_prompts(
    current_user: User = Depends(require_role([UserRole.HR_MANAGER, UserRole.ADMIN]))
):
    """Force reloads all agent prompts from Langfuse or local registry (Restricted to HR/Admin)."""
    langfuse_prompt_service._cache.clear()
    langfuse_prompt_service._load_local_registry()
    sync_agent_instructions()
    return {"status": "success", "message": "All agent prompts refreshed successfully across the ADK fleet."}


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

from app.services.langfuse_prompt_service import langfuse_prompt_service

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

@router.post("/webhooks/langfuse")
async def langfuse_prompt_webhook(payload: Dict[str, Any]):
    """Receives prompt update webhooks from Langfuse to dynamically refresh cache without redeployment."""
    res = langfuse_prompt_service.handle_webhook_event(payload)
    return res

from fastapi.responses import StreamingResponse
from app.agents.orchestrator import llm_root_orchestrator
from app.services.zoho_service import zoho_service
from app.memory.conversation_memory import conversation_memory

@router.post("/chat/stream")
async def stream_chat_with_multi_agent_system(
    payload: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Real-time Server-Sent Events (SSE) streaming thought traces, tool runs, and response tokens."""
    return StreamingResponse(
        llm_root_orchestrator.stream_message(
            db=db,
            user=current_user,
            message=payload.message,
            session_id=payload.session_id,
            target_agent=payload.target_agent
        ),
        media_type="text/event-stream"
    )

@router.post("/webhooks/zoho")
async def zoho_inbound_webhook(payload: Dict[str, Any]):
    """Receives real-time attendance and leave approval webhooks from Zoho People."""
    res = zoho_service.handle_inbound_webhook(payload)
    return res

@router.get("/memory/{session_id}")
async def get_session_memory(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Inspects multi-turn conversational turns and active extracted entity states."""
    history = await conversation_memory.get_history_async(session_id, db=db, limit=10)
    entities = conversation_memory.get_all_entities(session_id)
    return {
        "session_id": session_id,
        "turns_count": len(history),
        "history": history,
        "entities": entities,
        "storage_mode": "POSTGRESQL_CHECKPOINT"
    }

@router.delete("/memory/{session_id}")
async def clear_session_memory(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Flushes active multi-turn session memory."""
    await conversation_memory.clear_session_async(session_id, db=db)
    return {"status": "CLEARED", "session_id": session_id}

@router.get("/sessions")
async def get_user_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves all past checkpointed conversation sessions for the active user from PostgreSQL."""
    sessions = await conversation_memory.get_user_sessions_db(db, current_user.id)
    return {"user_id": current_user.id, "sessions_count": len(sessions), "sessions": sessions}


from app.evaluations.grid_evaluator import grid_evaluator
from app.core.config import settings

@router.post("/evaluations/run")
async def run_grid_evaluations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Executes automated Grid Evaluation matrix across statutory & safety benchmarks."""
    summary = await grid_evaluator.run_evaluation_summary(db)
    return summary

@router.get("/presets")
async def get_flow_circuit_presets():
    """Returns dynamic flow circuit presets configured for the active jurisdiction and organization."""
    jurisdiction = settings.DEFAULT_JURISDICTION.title()
    return {
        "organization": settings.ORGANIZATION_NAME,
        "jurisdiction": jurisdiction,
        "presets": [
            {
                "id": "leave",
                "label": "Leave Application",
                "sub": "EL / CL / SL Statutory Request",
                "query": "I want to apply for 3 days Casual Leave from next Monday",
                "targetAgent": "Leave Subagent",
                "targetId": "leave",
                "railStatus": "Input Rail: 0 Policy Conflicts",
                "icon": "Calendar"
            },
            {
                "id": "policy",
                "label": f"{jurisdiction} Law Graph RAG",
                "sub": "Statutory Overtime & Hours",
                "query": f"What is the maximum daily working hours and overtime pay under {jurisdiction} labor act?",
                "targetAgent": "Policy Graph RAG Subagent",
                "targetId": "policy",
                "railStatus": "Output Rail: Legal Citations Extracted",
                "icon": "FileText"
            },
            {
                "id": "timesheet",
                "label": "Timesheet Entry & Overtime",
                "sub": "Hours Logging & Audit",
                "query": "What is the statutory overtime rate if I work 11 hours on a project?",
                "targetAgent": "Timesheet Subagent",
                "targetId": "timesheet",
                "railStatus": "Dual Rail: Statutory Max & DPDP Scrubbed",
                "icon": "Clock"
            },
            {
                "id": "health",
                "label": "Occupational Health",
                "sub": "Sick Protocols & Doctor Certificate",
                "query": "Employee requesting 4 days of sick leave with fever, do I need a medical certificate?",
                "targetAgent": "Occupational Health Subagent",
                "targetId": "health",
                "railStatus": "Clinical Triage & HIPAA Sanitized",
                "icon": "HeartPulse"
            },
            {
                "id": "zoho",
                "label": "Zoho People HRMS Sync",
                "sub": "Live REST v2 Attendance & Records",
                "query": "Sync my attendance and leave records with Zoho People API.",
                "targetAgent": "Zoho People Subagent",
                "targetId": "zoho",
                "railStatus": "REST v2 Integration & Zero Raw PII",
                "icon": "RefreshCw"
            }
        ]
    }


# ── WebSocket Bidirectional Chat Endpoint (Google ADK Stream) ─────────────────

@router.websocket("/ws")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Bi-directional real-time chat via WebSocket.
    Client frame (JSON): {"message": "..."}
    Server frame (JSON): {"type": "connected"|"typing"|"chunk"|"done"|"error", ...}
    """
    await websocket.accept()

    # Authenticate or resolve demo user
    from app.core.security import decode_access_token
    from sqlalchemy.future import select

    current_user = None
    if token:
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            res = await db.execute(select(User).filter(User.id == payload.get("sub"), User.is_active == True))
    if not current_user:
        await websocket.send_text(json.dumps({"type": "error", "message": "Unauthorized: A valid authentication token is required to establish a WebSocket session."}))
        await websocket.close(code=4001)
        return

    actual_session = session_id or f"ws_{current_user.id[:8]}_{int(time.time())}"
    await websocket.send_text(json.dumps({
        "type": "connected",
        "session_id": actual_session,
        "message": f"Connected to PeopleOps ADK Multi-Agent Fleet as {current_user.full_name}.",
    }))

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
                user_msg = data.get("message", "").strip()
                target_agent = data.get("target_agent")
            except Exception:
                user_msg = raw_text.strip()
                target_agent = None

            if not user_msg:
                continue

            # Send typing feedback
            await websocket.send_text(json.dumps({"type": "typing", "session_id": actual_session}))

            # Process turn via root orchestrator
            response = await orchestrator.process_message(
                db=db,
                user=current_user,
                message=user_msg,
                session_id=actual_session,
                target_agent=target_agent,
            )

            # Stream words
            words = response.response.split(" ")
            for i in range(0, len(words), 3):
                chunk = " ".join(words[i:i+3]) + " "
                await websocket.send_text(json.dumps({"type": "chunk", "text": chunk}))
                await asyncio.sleep(0.015)

            # Send completion frame with telemetry
            await websocket.send_text(json.dumps({
                "type": "done",
                "session_id": actual_session,
                "agent_routed": response.agent_routed,
                "guardrail_status": response.guardrail_status,
                "citations": [c.model_dump() if hasattr(c, "model_dump") else c for c in response.citations],
                "structured_action": response.structured_action.model_dump() if response.structured_action and hasattr(response.structured_action, "model_dump") else response.structured_action,
                "latency_ms": response.latency_ms,
            }))

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_text(json.dumps({"type": "error", "message": str(exc)}))
        except Exception:
            pass




