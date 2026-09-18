from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.services.auth_service import get_current_user
from app.agents.orchestrator import orchestrator

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
