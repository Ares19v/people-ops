"""
Unit and integration tests for PeopleOps Google ADK Fleet and Decoupled Tools.
"""
import pytest
from app.agents.adk_fleet import hr_root_orchestrator, create_hr_runner
from app.tools.hr_tools import (
    get_leave_balances,
    calculate_leave_eligibility,
    get_timesheet_summary,
    check_statutory_compliance,
    get_occupational_health_guidelines,
)


def test_adk_fleet_hierarchy():
    """Verify Google ADK agent tree and subagents configuration."""
    assert hr_root_orchestrator.name == "hr_root_orchestrator"
    sub_names = [a.name for a in hr_root_orchestrator.sub_agents]
    assert "leave_agent" in sub_names
    assert "timesheet_agent" in sub_names
    assert "health_agent" in sub_names
    assert "policy_agent" in sub_names
    assert "zoho_agent" in sub_names

    runner = create_hr_runner()
    assert runner.agent.name == "hr_root_orchestrator"


@pytest.mark.asyncio
async def test_statutory_compliance_tool():
    """Verify statutory rule checking under Indian state acts."""
    # Test valid 8-hour day
    res_normal = await check_statutory_compliance(jurisdiction="MAHARASHTRA", hours_worked=8.0)
    assert res_normal["is_valid"] is True
    assert res_normal["status"] == "APPROVED"

    # Test overtime warning (>9 hours)
    res_ot = await check_statutory_compliance(jurisdiction="MAHARASHTRA", hours_worked=10.0)
    assert res_ot["is_valid"] is True
    assert any("Overtime Incurred" in f for f in res_ot["findings"])

    # Test statutory cap breach (>11 hours)
    res_violation = await check_statutory_compliance(jurisdiction="MAHARASHTRA", hours_worked=12.5)
    assert res_violation["is_valid"] is False
    assert res_violation["status"] == "VIOLATION_DETECTED"


@pytest.mark.asyncio
async def test_leave_tools_contract():
    """Verify leave tools error resilience and calculation contracts."""
    # Test invalid date range returns error dict, not exception
    eligibility = await calculate_leave_eligibility(
        user_id="usr_test_01",
        leave_type="CL",
        start_date="2026-10-15",
        end_date="2026-10-10",
    )
    assert "error" in eligibility
    assert "end_date cannot precede start_date" in eligibility["error"]


@pytest.mark.asyncio
async def test_occupational_health_guidelines():
    """Verify occupational health protocols for single vs extended illness."""
    # Mild symptom
    mild = await get_occupational_health_guidelines("headache")
    assert mild["requires_doctor_certificate"] is False

    # Extended / critical illness
    severe = await get_occupational_health_guidelines("high fever and hospital admission")
    assert severe["requires_doctor_certificate"] is True
    assert "ESI Act" in severe["protocol"]
