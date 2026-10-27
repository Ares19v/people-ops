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
async def test_db_prompts_are_audit_only_and_do_not_change_active_agents():
    """Langfuse is the sole authority for agent prompts; DB rows are a historical audit log."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Loading from the DB is deprecated and must not seed or mutate anything.
        assert isinstance(await langfuse_prompt_service.load_prompts_from_db(session), int)

        first = await langfuse_prompt_service.save_prompt_to_db(
            prompt_key="audit-test-prompt", template="AUDIT_V1", db=session
        )
        second = await langfuse_prompt_service.save_prompt_to_db(
            prompt_key="audit-test-prompt", template="AUDIT_V2", db=session
        )
        assert second["version"] == first["version"] + 1

        res = await session.execute(select(AgentPrompt).where(AgentPrompt.prompt_key == "audit-test-prompt"))
        record = res.scalar_one()
        assert record.template == "AUDIT_V2"

    # Audit rows never leak into the live prompt cache or the ADK fleet.
    assert langfuse_prompt_service.get_prompt("audit-test-prompt") != "AUDIT_V2"
    sync_agent_instructions()
    assert "AUDIT_V" not in leave_agent.instruction


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
        assert "leave balance" in summary_text.lower()

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
        assert "AUTHENTICATED EMPLOYEE:" in formatted and "emp_test_123" in formatted
        assert "Current Session In-Progress Summary" in formatted

        # Verify turns table contains turn_metadata
        stmt = select(ChatTurn).where(ChatTurn.session_id == test_session_id)
        res = await session.execute(stmt)
        db_turns = res.scalars().all()
        assert len(db_turns) == 7
        assert db_turns[0].turn_metadata.get("turn_idx") == 0


@pytest.mark.asyncio
async def test_prompts_crud_endpoint_integration(monkeypatch):
    """GET /prompts, and PUT /prompts against a fake Langfuse client (never the real cloud project)."""
    import types
    from httpx import AsyncClient, ASGITransport

    created = {}

    def create_prompt(**kw):
        created.update(kw)
        return types.SimpleNamespace(version=9)

    monkeypatch.setitem(langfuse_prompt_service._cache, "timesheet-subagent", langfuse_prompt_service._cache["timesheet-subagent"])
    monkeypatch.setattr(langfuse_prompt_service, "_langfuse_client", types.SimpleNamespace(create_prompt=create_prompt))

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
        assert created["name"] == "timesheet-subagent" and created["prompt"] == put_payload["template"]

        # Check prompt in memory and DB
        assert langfuse_prompt_service.get_prompt("timesheet-subagent") == put_payload["template"]


@pytest.mark.asyncio
async def test_prompt_edit_is_rejected_when_langfuse_is_not_connected(monkeypatch):
    """Langfuse is the only place prompts can be edited; without it the API must refuse, not silently succeed."""
    from httpx import AsyncClient, ASGITransport

    monkeypatch.setattr(langfuse_prompt_service, "_langfuse_client", None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login = await client.post("/api/v1/auth/mock-login", json={"role": "HR_MANAGER"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        res = await client.put("/api/v1/agents/prompts/timesheet-subagent", json={"template": "X", "label": "live"}, headers=headers)
        assert res.status_code == 400


def test_websocket_chat_flow():
    """Verify WebSocket real-time connection and greeting frame."""
    client = TestClient(app)
    login = client.post("/api/v1/auth/mock-login", json={"role": "EMPLOYEE"})
    token = login.json()["access_token"]
    with client.websocket_connect(f"/api/v1/agents/ws?token={token}") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "connected"
        assert "Connected to PeopleOps ADK Multi-Agent Fleet" in data["message"]
