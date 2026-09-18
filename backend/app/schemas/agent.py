from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class CitationItem(BaseModel):
    source_title: str
    section: str
    document_type: str # STATUTORY_LAW, COMPANY_POLICY, or CONFIGURATION
    citation_text: str
    confidence_score: float = 1.0

class StructuredAction(BaseModel):
    action_type: str # e.g. "LEAVE_APPLY", "LEAVE_CANCEL", "TIMESHEET_LOG", "ESCALATE_HR"
    action_payload: Dict[str, Any]
    requires_confirmation: bool = True
    executed: bool = False
    result_message: Optional[str] = None

class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    target_agent: Optional[str] = None # Optional override: "LEAVE", "POLICY", "TIMESHEET"

class AgentChatResponse(BaseModel):
    response: str
    agent_routed: str # "ORCHESTRATOR", "LEAVE_AGENT", "POLICY_AGENT", "TIMESHEET_AGENT"
    guardrail_status: str # "PASSED", "INPUT_BLOCKED", "OUTPUT_SCRUBBED"
    guardrail_tripped: Optional[str] = None
    citations: List[CitationItem] = []
    structured_action: Optional[StructuredAction] = None
    session_id: str
    latency_ms: float
    token_usage: Dict[str, int] = {}
