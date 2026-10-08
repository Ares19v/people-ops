import pytest
from app.services.langfuse_prompt_service import langfuse_prompt_service
from app.memory.conversation_memory import conversation_memory
from app.services.zoho_service import zoho_service
from app.agents.orchestrator import llm_root_orchestrator
from app.evaluations.grid_evaluator import grid_evaluator, GRID_DATASET
from app.models.user import User, UserRole

@pytest.fixture
def mock_user():
    return User(
        id="usr-test-101",
        email="test.emp@intelera.com",
        full_name="Vikram Sethi",
        role=UserRole.EMPLOYEE,
        is_active=True
    )

def test_langfuse_prompt_service_loading():
    # Verify prompt is loaded decoupled from python code
    prompt = langfuse_prompt_service.get_prompt("peopleops-root-orchestrator")
    assert "PeopleOps Enterprise Root Orchestrator" in prompt
    assert "PRIVACY BOUNDARY" in prompt

def test_langfuse_prompt_webhook_invalidation():
    # Verify webhook listener invalidates cache dynamically
    payload = {"event": "prompt.updated", "prompt_name": "peopleops-root-orchestrator"}
    res = langfuse_prompt_service.handle_webhook_event(payload)
    assert res["status"] == "success"
    assert res["prompt_invalidated"] == "peopleops-root-orchestrator"

def test_conversational_memory_turn_retention():
    session_id = "mem-session-999"
    conversation_memory.clear_session(session_id)

    # Turn 1
    conversation_memory.add_turn(session_id, "user", "I want to take 3 days of sick leave next week.")
    conversation_memory.add_turn(session_id, "assistant", "Sick leave for 3 days noted. A medical certificate is required.")

    # Turn 2
    conversation_memory.add_turn(session_id, "user", "Actually make that 4 days.")

    history = conversation_memory.get_formatted_history(session_id)
    assert "take 3 days of sick leave" in history
    assert "Actually make that 4 days" in history

@pytest.mark.asyncio
async def test_zoho_service_integration():
    records = await zoho_service.get_leave_records("EMP-555")
    assert len(records) >= 2
    assert records[0].leave_type == "Earned Leave"
    assert records[0].status == "Approved"

    emp_profile = await zoho_service.get_employee_record("vikram@intelera.com")
    assert emp_profile.employee_id == "INTEL-104"
    assert emp_profile.designation == "Senior Systems Architect"

@pytest.mark.asyncio
async def test_llm_root_orchestrator_zoho_tool_delegation(mock_user):
    resp = await llm_root_orchestrator.process_message(
        db=None,
        user=mock_user,
        message="Sync my attendance and leave records with Zoho People API",
        session_id="sess-zoho-test"
    )
    assert "ZOHO_SUBAGENT" in resp.agent_routed
    assert "Zoho People System Sync" in resp.response
    assert len(resp.citations) > 0

@pytest.mark.asyncio
async def test_llm_root_orchestrator_multi_turn_memory(mock_user):
    session_id = "sess-memory-flow"
    conversation_memory.clear_session(session_id)

    # Turn 1: Inquire about sick leave
    resp1 = await llm_root_orchestrator.process_message(
        db=None,
        user=mock_user,
        message="Employee: Vikram Sethi feeling unwell with fever, need sick leave.",
        session_id=session_id
    )
    assert "HEALTH_SUBAGENT" in resp1.agent_routed
    assert "Vikram Sethi" not in resp1.response  # PII masked for EMPLOYEE role!

    # Turn 2: Follow-up question relying on memory
    resp2 = await llm_root_orchestrator.process_message(
        db=None,
        user=mock_user,
        message="Do I need to submit a doctor certificate for this absence?",
        session_id=session_id
    )
    assert "doctor" in resp2.response.lower() or "medical" in resp2.response.lower()

@pytest.mark.asyncio
async def test_grid_evaluator_statutory_and_safety_scores():
    # Run evaluation on the test cases
    results = await grid_evaluator.run_grid_evaluation(db=None)
    assert len(results) == len(GRID_DATASET)
    for r in results:
        assert r.safety_score == 1.0  # Zero PII leaks across all test evaluations!
        assert r.groundedness_score >= 0.50

def test_statutory_critic_self_correction():
    from app.agents.statutory_critic import statutory_critic
    flawed_text = "Your overtime multiplier is 1.5x and the overtime cap is 50 hours."
    result = statutory_critic.verify_and_correct(flawed_text)
    assert not result.is_valid
    assert result.corrections_applied >= 1
    assert "twice the ordinary rate of wages (2.0x)" in result.corrected_text
    assert "Section 14" in result.corrected_text

def test_zoho_circuit_breaker_and_webhook():
    # Test Circuit Breaker
    cb = zoho_service.circuit_breaker
    cb.record_success()
    assert cb.allow_request()

    # Test Inbound Webhook
    webhook_payload = {
        "event": "LEAVE_APPROVAL",
        "record_id": "ZOHO-LV-901",
        "status": "Approved",
        "approver": "HR Manager (Sneha Rao)"
    }
    webhook_res = zoho_service.handle_inbound_webhook(webhook_payload)
    assert webhook_res["status"] == "PROCESSED"
    assert webhook_res["record_id"] == "ZOHO-LV-901"
    assert webhook_res["new_status"] == "Approved"

@pytest.mark.asyncio
async def test_streaming_sse_generator(mock_user):
    events = []
    async for chunk in llm_root_orchestrator.stream_message(
        db=None,
        user=mock_user,
        message="What is the statutory overtime rate under Section 14?",
        session_id="sess-stream-test"
    ):
        events.append(chunk)

    assert len(events) > 0
    full_stream = "".join(events)
    assert "event: status" in full_stream
    assert "event: thought" in full_stream
    assert "event: complete" in full_stream

