"""Test Suite for Database-Backed Dynamic Prompts, Fleet Hot-Reload & Rolling Memory Summaries."""

import pytest
import uuid
import time
from sqlalchemy import select
from fastapi.testclient import TestClient

from app.core.database import AsyncSessionLocal, engine, Base
from app.models.prompt import AgentPrompt
from app.models.chat_session import ChatSession, ChatTurn, ConversationSummary
from app.models.user import User, UserRole
from app.services.langfuse_prompt_service import langfuse_prompt_service
from app.memory.conversation_memory import conversation_memory, ConversationMemoryManager
from app.agents.adk_fleet import leave_agent, sync_agent_instructions
from app.main import app


@pytest.mark.asyncio
async def test_db_prompt_seeding_and_hot_reload():
    """Verify that agent prompts are seeded into DB, updated, and hot-reloaded into active ADK agents."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # 1. Seed from registry to DB
        count = await langfuse_prompt_service.load_prompts_from_db(session)
        assert count >= 5, f"Expected at least 5 prompts seeded, got {count}"

        # 2. Check DB records
        stmt = select(AgentPrompt).where(AgentPrompt.prompt_key == "leave-subagent")
        res = await session.execute(stmt)
        record = res.scalar_one_or_none()
        assert record is not None
        assert record.version >= 1
        assert "Leave" in record.template or "leave" in record.template

        initial_version = record.version

        # 3. Update prompt in DB and verify hot reload
        new_instruction = "UPDATED_TEST_LEAVE_INSTRUCTION: Always prioritize statutory maternity leaves."
        saved = await langfuse_prompt_service.save_prompt_to_db(
            prompt_key="leave-subagent",
            template=new_instruction,
            db=session
        )
        assert saved["version"] == initial_version + 1

        # 4. In-memory cache must reflect it immediately
        cached = langfuse_prompt_service.get_prompt("leave-subagent")
        assert cached == new_instruction

        # 5. Active ADK fleet instance must have updated instruction
        sync_agent_instructions()
        assert leave_agent.instruction == new_instruction


@pytest.mark.asyncio
async def test_rolling_conversational_summaries_and_identity_context():
    """Verify that long sessions trigger rolling summaries and inject user context."""
    test_session_id = f"test_sess_{uuid.uuid4().hex[:8]}"
    mem = ConversationMemoryManager(summary_threshold=5)

    async with AsyncSessionLocal() as session:
        # Seed 7 turns
        for i in range(7):
            role = "user" if i % 2 == 0 else "assistant"
            content = f"Turn {i}: Discussion regarding leave balance calculation {i}."
            await mem.persist_turn_db(
                db=session,
                session_id=test_session_id,
                user_id="emp_test_123",
                role=role,
                content=content,
                metadata={"turn_idx": i, "latency_ms": 120}
            )

        # Verify summary was generated
        assert test_session_id in mem._summaries
        summary_text = mem._summaries[test_session_id]
        assert "Prior conversation covered" in summary_text

        # Verify summary was checkpointed in database
        stmt = select(ConversationSummary).where(ConversationSummary.session_id == test_session_id)
        res = await session.execute(stmt)
        db_summary = res.scalar_one_or_none()
        assert db_summary is not None
        assert db_summary.summary_text == summary_text

        # Verify formatted history includes context header & rolling summary
        formatted = mem.get_formatted_history(
            session_id=test_session_id,
            limit=4,
            user_id="emp_test_123",
            user_role="EMPLOYEE"
        )
        assert "AUTHENTICATED USER: emp_test_123" in formatted
        assert "Previous Conversation Rolling Summary" in formatted

        # Verify turns table contains turn_metadata
        stmt = select(ChatTurn).where(ChatTurn.session_id == test_session_id)
        res = await session.execute(stmt)
        db_turns = res.scalars().all()
        assert len(db_turns) == 7
        assert db_turns[0].turn_metadata.get("turn_idx") == 0


@pytest.mark.asyncio
async def test_prompts_crud_endpoint_integration():
    """Verify GET /prompts and PUT /prompts endpoints using test client."""
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Mock login as HR Manager
        login = await client.post("/api/v1/auth/mock-login", json={"role": "HR_MANAGER"})
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # GET prompts
        get_res = await client.get("/api/v1/agents/prompts", headers=headers)
        assert get_res.status_code == 200
        data = get_res.json()
        assert "prompts" in data
        assert "db_records" in data

        # PUT prompt
        put_payload = {
            "template": "CUSTOMIZED_PROMPT: Check Maharashtra Shops Act 2017.",
            "label": "production"
        }
        put_res = await client.put(
            "/api/v1/agents/prompts/timesheet-subagent",
            json=put_payload,
            headers=headers
        )
        assert put_res.status_code == 200
        assert put_res.json()["status"] == "success"

        # Check prompt in memory and DB
        assert langfuse_prompt_service.get_prompt("timesheet-subagent") == put_payload["template"]


def test_websocket_chat_flow():
    """Verify WebSocket real-time connection and greeting frame."""
    client = TestClient(app)
    login = client.post("/api/v1/auth/mock-login", json={"role": "EMPLOYEE"})
    token = login.json()["access_token"]
    with client.websocket_connect(f"/api/v1/agents/ws?token={token}") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "connected"
        assert "Connected to PeopleOps ADK Multi-Agent Fleet" in data["message"]
