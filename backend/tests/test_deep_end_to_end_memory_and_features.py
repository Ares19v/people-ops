"""Deep End-to-End Verification Test Suite.

Rigorously tests:
1. Multi-turn conversational memory continuity (the agent remembers across turns)
2. Entity state retention and disk snapshot reload (persistence across server reboots)
3. Zero-PII reversible cryptographic vault boundary (DPDP Act 2023)
4. Statutory Critic self-reflection and invariant enforcement (Maharashtra Act 2017)
5. Compound concurrent subagent tool execution
6. Real-time Server-Sent Events (SSE) streaming
7. Zoho People API circuit breaker and inbound webhook pipeline
8. Grid Evaluator automated regression suite
"""

import os
import pytest
from app.models.user import User, UserRole
from app.memory.conversation_memory import ConversationMemoryManager, conversation_memory
from app.agents.orchestrator import llm_root_orchestrator
from app.agents.statutory_critic import statutory_critic
from app.compliance.phi_engine import compliance_engine
from app.services.zoho_service import zoho_service
from app.services.langfuse_prompt_service import langfuse_prompt_service
from app.evaluations.grid_evaluator import grid_evaluator

@pytest.fixture
def test_employee():
    return User(
        id="usr-emp-7701",
        email="aarav.patel@intelera.com",
        full_name="Aarav Patel",
        role=UserRole.EMPLOYEE,
        is_active=True
    )

@pytest.fixture
def test_hr_admin():
    return User(
        id="usr-adm-8801",
        email="sneha.rao@intelera.com",
        full_name="Sneha Rao",
        role=UserRole.HR_MANAGER,
        is_active=True
    )

# =========================================================================
# 1. SCENARIO 1: Multi-Turn Memory Continuity (The Agent Remembers)
# =========================================================================
@pytest.mark.asyncio
async def test_scenario_multi_turn_conversational_continuity(test_employee):
    """Verifies that the agent remembers leave parameters from Turn 1 when modified in Turn 2."""
    session_id = f"test_e2e_continuity_{os.getpid()}"
    conversation_memory.clear_session(session_id)

    # Turn 1: Inbound request with duration and start date
    turn1_msg = "I want to apply for 3 days Casual Leave from next Monday."
    resp1 = await llm_root_orchestrator.process_message(
        db=None,
        user=test_employee,
        message=turn1_msg,
        session_id=session_id
    )
    assert resp1.response is not None
    assert "Casual Leave" in resp1.response or "CL" in resp1.response or "balance" in resp1.response.lower()

    # Verify extracted entity state
    entities = conversation_memory.get_all_entities(session_id)
    assert entities.get("active_leave_type") == "Casual Leave (CL)"
    assert entities.get("active_duration_days") == 3
    assert entities.get("active_start_date") == "Next Monday"

    # Turn 2: Follow-up modifying category without repeating dates
    turn2_msg = "Actually, can I make that Earned Leave instead?"
    resp2 = await llm_root_orchestrator.process_message(
        db=None,
        user=test_employee,
        message=turn2_msg,
        session_id=session_id
    )

    # Agent should recall duration and start date from Turn 1
    history = conversation_memory.get_formatted_history(session_id)
    assert "Casual Leave" in history
    assert "Earned Leave" in history
    updated_entities = conversation_memory.get_all_entities(session_id)
    assert updated_entities.get("active_leave_type") == "Earned Leave (EL)"
    assert updated_entities.get("active_duration_days") == 3

    # Turn 3: Inquire about carry-forward rules for this specific leave
    turn3_msg = "Will this leave carry forward to next year if I don't use it?"
    resp3 = await llm_root_orchestrator.process_message(
        db=None,
        user=test_employee,
        message=turn3_msg,
        session_id=session_id
    )
    # Must cite Section 18 statutory carry-forward cap (45 days)
    assert "45" in resp3.response
    assert "Section 18" in resp3.response or "Maharashtra" in resp3.response

# =========================================================================
# 2. SCENARIO 2: Disk Snapshot Persistence Across Reboots
# =========================================================================
def test_scenario_memory_disk_snapshot_persistence():
    """Simulates a complete server crash/reboot by reloading memory from disk."""
    session_id = "test_persistence_reboot_sim"
    conversation_memory.clear_session(session_id)

    # Seed turns and entities
    conversation_memory.add_turn(session_id, "user", "I need 2 days leave for medical checkup.")
    conversation_memory.add_turn(session_id, "assistant", "Medical leave noted. Please provide doctor slip.")
    conversation_memory.set_entity(session_id, "doctor_slip_required", True)

    # Force save
    conversation_memory._save_to_disk()

    # Create fresh manager simulating new process start
    new_memory_mgr = ConversationMemoryManager()
    reloaded_history = new_memory_mgr.get_history(session_id)
    reloaded_entities = new_memory_mgr.get_all_entities(session_id)

    assert len(reloaded_history) >= 2
    assert "medical checkup" in reloaded_history[0]["content"]
    assert reloaded_entities.get("doctor_slip_required") is True

# =========================================================================
# 2b. SCENARIO 2b: PostgreSQL Session & Turn Checkpointing
# =========================================================================
@pytest.mark.asyncio
async def test_scenario_postgresql_session_checkpointing(test_employee):
    """Verifies that conversation sessions and turns checkpoint to PostgreSQL tables."""
    from app.core.database import AsyncSessionLocal
    from app.models.chat_session import ChatSession, ChatTurn
    from sqlalchemy import select

    session_id = f"test_pg_checkpoint_{os.getpid()}"
    async with AsyncSessionLocal() as db:
        await conversation_memory.clear_session_async(session_id, db=db)

        turn1 = await conversation_memory.persist_turn_db(
            db=db,
            session_id=session_id,
            user_id=test_employee.id,
            role="user",
            content="I am applying for 3 days Casual Leave next week.",
            metadata={"source": "pytest"}
        )
        assert turn1.role == "user"

        turn2 = await conversation_memory.persist_turn_db(
            db=db,
            session_id=session_id,
            user_id=test_employee.id,
            role="assistant",
            content="Casual leave request prepared for 3 days.",
            metadata={"source": "pytest"}
        )
        assert turn2.role == "assistant"

        sess_stmt = select(ChatSession).filter(ChatSession.id == session_id)
        sess_res = await db.execute(sess_stmt)
        saved_sess = sess_res.scalar_one_or_none()
        assert saved_sess is not None
        assert saved_sess.user_id == test_employee.id
        assert saved_sess.active_slots.get("active_leave_type") == "Casual Leave (CL)"

        turns_stmt = select(ChatTurn).filter(ChatTurn.session_id == session_id).order_by(ChatTurn.created_at.asc())
        turns_res = await db.execute(turns_stmt)
        saved_turns = turns_res.scalars().all()
        assert len(saved_turns) == 2
        assert saved_turns[0].role == "user"
        assert saved_turns[1].role == "assistant"

        history = await conversation_memory.get_history_async(session_id, db=db, limit=5)
        assert len(history) == 2

        user_sessions = await conversation_memory.get_user_sessions_db(db, test_employee.id)
        assert any(s["session_id"] == session_id for s in user_sessions)

        await conversation_memory.clear_session_async(session_id, db=db)


# =========================================================================
# 3. SCENARIO 3: Zero-PII Cryptographic Vault Boundary
# =========================================================================
def test_scenario_zero_pii_vault_and_role_access():
    """Ensures raw Aadhaar and PAN numbers never leave to external tools, and role masking works."""
    raw_text = "Employee Aarav Patel PAN ABCDE1234F Aadhaar 8877 6655 4433 applying for loan."
    session_id = "sess_pii_vault_test"

    redaction = compliance_engine.redact(raw_text, session_id=session_id)
    redacted = redaction.redacted_text

    # Raw identifiers MUST NOT exist in redacted string
    assert "ABCDE1234F" not in redacted
    assert "8877 6655 4433" not in redacted
    assert "[PAN_" in redacted
    assert "[AADHAAR_" in redacted

    # De-redaction by unauthorized Employee role -> Masked format
    emp_view = compliance_engine.de_redact(redacted, session_id=session_id, user_role="Employee")
    assert "ABCDE1234F" not in emp_view
    assert "XXXX" in emp_view

    # De-redaction by authorized HR Manager role -> Full plaintext restored
    admin_view = compliance_engine.de_redact(redacted, session_id=session_id, user_role="HR_Manager")
    assert "ABCDE1234F" in admin_view
    assert "8877 6655 4433" in admin_view

# =========================================================================
# 4. SCENARIO 4: Statutory Critic Self-Reflection Verification
# =========================================================================
def test_scenario_statutory_critic_invariants():
    """Asserts that all statutory rules under Maharashtra Act 2017 are defended against hallucinations."""
    # Test 1: Overtime multiplier hallucination (1.5x -> 2.0x)
    hallucinated_text = "As per company guidelines, overtime is paid at 1.5x the base hourly rate."
    critique1 = statutory_critic.verify_and_correct(hallucinated_text)
    assert not critique1.is_valid
    assert "twice the ordinary rate of wages (2.0x)" in critique1.corrected_text
    assert "Section 14" in critique1.corrected_text

    # Test 2: Overtime quarterly limit hallucination
    hallucinated_cap = "Your quarterly overtime limit is 60 hours."
    critique2 = statutory_critic.verify_and_correct(hallucinated_cap)
    assert not critique2.is_valid
    assert "maximum of 125 hours per quarter" in critique2.corrected_text

    # Test 3: Earned Leave carry-forward hallucination
    hallucinated_carry = "You can carry forward up to 60 days of earned leave."
    critique3 = statutory_critic.verify_and_correct(hallucinated_carry)
    assert not critique3.is_valid
    assert "maximum carry-forward accumulation of 45 days" in critique3.corrected_text

# =========================================================================
# 5. SCENARIO 5: Compound Parallel Tool Execution
# =========================================================================
@pytest.mark.asyncio
async def test_scenario_compound_parallel_tool_dispatch(test_employee):
    """Verifies that compound queries invoke multiple specialized subagents in parallel."""
    compound_query = "What is the statutory policy for overtime under Section 14, and please sync my Zoho attendance records?"
    session_id = "sess_compound_parallel"

    resp = await llm_root_orchestrator.process_message(
        db=None,
        user=test_employee,
        message=compound_query,
        session_id=session_id
    )

    # Should dispatch concurrently
    assert "CONCURRENT" in resp.agent_routed
    assert "TIMESHEET_SUBAGENT" in resp.agent_routed or "POLICY_RAG_SUBAGENT" in resp.agent_routed
    assert "ZOHO_SUBAGENT" in resp.agent_routed
    assert "Zoho People System Sync" in resp.response
    assert "Section 14" in resp.response or "2.0x" in resp.response or "twice" in resp.response

# =========================================================================
# 6. SCENARIO 6: Server-Sent Events (SSE) Streaming Trace
# =========================================================================
@pytest.mark.asyncio
async def test_scenario_sse_streaming_protocol(test_employee):
    """Validates that real-time thought traces and tokens are emitted adhering to the SSE standard."""
    stream_events = []
    async for chunk in llm_root_orchestrator.stream_message(
        db=None,
        user=test_employee,
        message="What is the maximum daily working hours limit under Maharashtra Act 2017?",
        session_id="sess_sse_test"
    ):
        stream_events.append(chunk)

    full_output = "".join(stream_events)
    assert "event: status" in full_output
    assert "event: thought" in full_output
    assert "event: tool_start" in full_output
    assert "event: tool_done" in full_output
    assert "event: critic" in full_output
    assert "event: token" in full_output
    assert "event: complete" in full_output

# =========================================================================
# 7. SCENARIO 7: Zoho People Circuit Breaker Resilience
# =========================================================================
@pytest.mark.asyncio
async def test_scenario_zoho_circuit_breaker_recovery():
    """Tests circuit breaker failure tripping, recovery, and fallback."""
    cb = zoho_service.circuit_breaker
    cb.record_success()
    assert cb.state.value == "CLOSED"

    # Trip breaker
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state.value == "OPEN"

    # When OPEN, requests fall back seamlessly without crashing
    records = await zoho_service.get_leave_records("EMP-TEST")
    assert len(records) >= 2

    # Reset
    cb.record_success()
    assert cb.state.value == "CLOSED"

# =========================================================================
# 8. SCENARIO 8: Automated Grid Evaluation Summary
# =========================================================================
@pytest.mark.asyncio
async def test_scenario_grid_evaluator_summary_metrics():
    """Runs the complete Grid Evaluation suite and asserts strict quality thresholds."""
    summary = await grid_evaluator.run_evaluation_summary(db=None)

    assert summary["total_test_cases"] == 5
    assert summary["pass_rate_pct"] >= 80.0
    assert summary["mean_safety_score"] == 1.0  # Zero PII leakage
    assert summary["mean_groundedness_score"] >= 0.60
    assert summary["mean_latency_ms"] < 25000.0
