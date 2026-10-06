import pytest
from app.compliance.phi_engine import compliance_engine
from app.compliance.hipaa_rules import ComplianceCategory
from app.guardrails.guardrails_manager import guardrails_manager
from app.rag.chunking import hierarchical_chunker
from app.rag.knowledge_graph import enterprise_knowledge_graph
from app.rag.hybrid_retriever import hybrid_policy_retriever
from app.rag.agentic_rag import agentic_policy_rag
from app.agents.langgraph_orchestrator import enterprise_agent_graph
from app.agents.prompt_strategies import generate_statutory_cot_prompt, StructuredStatutoryAssessment, StatutoryIntent
from app.observability.langsmith_tracer import langsmith_tracer

def test_regulatory_hipaa_dpdp_identification():
    text = (
        "Candidate: Ramesh Sharma with Aadhaar 4455 6677 8899 and PAN ABCDE1234F. "
        "Medical Record MRN-778899 and Health Plan ID POL-99887766."
    )
    entities = compliance_engine.identify_entities(text)
    categories = [e.category for e in entities]

    assert ComplianceCategory.AADHAAR in categories
    assert ComplianceCategory.PAN in categories
    assert ComplianceCategory.MRN in categories
    assert ComplianceCategory.HEALTH_PLAN_ID in categories
    assert ComplianceCategory.NAME in categories

def test_compliance_redaction_and_reversible_deredaction():
    session_id = "test-sess-hr-001"
    raw_text = "Employee: Priya Patel submitted doctor certificate for sick leave with Policy ID POL-11223344."

    # 1. Redact
    redaction = compliance_engine.redact(raw_text, session_id=session_id)
    assert "Priya Patel" not in redaction.redacted_text
    assert "POL-11223344" not in redaction.redacted_text
    assert "[NAME_1]" in redaction.redacted_text or "[NAME_" in redaction.redacted_text

    # 2. De-redact as HR Manager (Authorized)
    restored = compliance_engine.de_redact(redaction.redacted_text, session_id=session_id, user_role="HR_Manager")
    assert "Priya Patel" in restored
    assert "POL-11223344" in restored

    # 3. De-redact as unauthorized role (Masked)
    masked = compliance_engine.de_redact(redaction.redacted_text, session_id=session_id, user_role="Employee")
    assert "Priya Patel" not in masked
    assert "REDACTED" in masked

def test_emergency_medical_input_guardrail():
    urgent_msg = "Employee collapsed on office floor with severe crushing chest pressure and left arm pain!"
    is_safe, trip_reason, refusal_msg = guardrails_manager.check_input(urgent_msg, "EMPLOYEE")
    
    assert not is_safe
    assert trip_reason == "EMERGENCY_TRIAGE_ESCALATION"
    assert "EMERGENCY MEDICAL ALERT" in refusal_msg

def test_hierarchical_markdown_chunking():
    md = "# Chapter 1: Leave Rules\nAll leave rules.\n## Section 18: Statutory Accrual\n1 day per 20 days."
    chunks = hierarchical_chunker.chunk_markdown(md, doc_name="Labour_Act")
    assert len(chunks) == 2
    assert chunks[0].section_title == "Chapter 1: Leave Rules"
    assert chunks[1].section_title == "Section 18: Statutory Accrual"

def test_networkx_policy_knowledge_graph():
    res = enterprise_knowledge_graph.search_graph("Earned leave carry forward and statutory accrual")
    assert len(res.statutory_mandates) > 0
    assert any("Section_18" in m["source"] for m in res.statutory_mandates)

def test_hybrid_rrf_retrieval():
    query = "casual leave quota maharashtra shops"
    passages = hybrid_policy_retriever.search_hybrid_rrf(query, top_k=2)
    assert len(passages) > 0
    assert passages[0].rrf_score > 0
    assert "Casual Leave" in passages[0].content or "Maharashtra" in passages[0].content

def test_agentic_policy_rag():
    query = "What is the statutory overtime wage rate under Maharashtra Act?"
    res = agentic_policy_rag.search_and_synthesize(query, top_k=2)
    assert len(res.citations) > 0
    assert "Section" in res.synthesis or "Overtime" in res.synthesis

def test_langgraph_enterprise_orchestrator():
    initial_state = {
        "session_id": "test-lg-sess",
        "user_id": "usr-123",
        "user_role": "HR_Manager",
        "raw_input": "Employee: Anita Desai requesting 4 days of sick leave due to medical illness.",
        "redacted_input": "",
        "phi_detected_count": 0,
        "guardrail_status": "",
        "guardrail_tripped": None,
        "routed_agent": "",
        "agent_output": "",
        "citations": [],
        "structured_action": None,
        "requires_hitl_approval": False,
        "is_approved": False,
        "final_response": "",
        "duration_ms": 0.0,
    }

    result = enterprise_agent_graph.invoke(initial_state)

    assert result["routed_agent"] == "HEALTH_AGENT"
    assert result["phi_detected_count"] >= 1
    assert "Sick Leave Quota" in result["final_response"]
    assert "Anita Desai" in result["final_response"]  # Reversibly de-redacted for HR_Manager!

def test_prompt_strategies_cot_and_structured_output():
    prompt = generate_statutory_cot_prompt("Employee completed 240 days, apply 10 days EL")
    assert "Maharashtra Shops & Establishments Act, 2017" in prompt
    assert "Chain-of-Thought" in prompt

    assessment = StructuredStatutoryAssessment(
        intent=StatutoryIntent.LEAVE_APPLICATION,
        applicable_statutory_sections=["Section 18(1)(a)"],
        entitlement_days=18.0,
        requires_medical_certificate=False,
        requires_manager_approval=True,
        cot_reasoning="Accrual checked against 240 days worked."
    )
    assert assessment.intent == StatutoryIntent.LEAVE_APPLICATION
    assert assessment.entitlement_days == 18.0

def test_dual_observability_tracing():
    payload = langsmith_tracer.trace_agent_run(
        session_id="obs-sess-1",
        user_id="usr-99",
        user_role="HR_Manager",
        agent_name="HEALTH_AGENT",
        raw_input="Employee Aadhaar 1234 5678 9012 submitted medical claim",
        sanitized_output="Claim processed with sum insured INR 5,00,000",
        guardrail_status="PASSED",
        guardrail_tripped=None,
        duration_ms=45.2,
        token_usage={"total_tokens": 30},
        safety_score=1.0
    )
    assert "1234 5678 9012" not in payload["input"]
    assert "XXXX-XXXX-9012" in payload["input"]
    assert payload["safety_score"] == 1.0
