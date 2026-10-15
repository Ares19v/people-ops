"""Prompt Engineering Strategies for Enterprise HR and Occupational Health Workflows.

Demonstrates:
1. System Prompt Strategy (Role constraints, statutory liability, zero-PHI directives).
2. Few-Shot In-Context Prompting for Statutory & Medical Leaves.
3. Chain-of-Thought (CoT) Statutory Reconciliation Reasoning.
4. Structured Outputs with Pydantic for deterministic action execution.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class StatutoryIntent(str, Enum):
    LEAVE_APPLICATION = "LEAVE_APPLICATION"
    POLICY_QUERY = "POLICY_QUERY"
    TIMESHEET_LOGGING = "TIMESHEET_LOGGING"
    OCCUPATIONAL_HEALTH = "OCCUPATIONAL_HEALTH"
    SENSITIVE_LEGAL_ESCALATION = "SENSITIVE_LEGAL_ESCALATION"

class StructuredStatutoryAssessment(BaseModel):
    intent: StatutoryIntent = Field(..., description="Classified intent")
    applicable_statutory_sections: List[str] = Field(default_factory=list, description="Sections e.g. Section 18(1)(a), Section 13")
    entitlement_days: Optional[float] = Field(None, description="Calculated leave quota or working hour cap")
    requires_medical_certificate: bool = Field(False, description="True if sick leave exceeds 2 consecutive days")
    requires_manager_approval: bool = Field(True, description="True for all state-changing actions")
    cot_reasoning: str = Field(..., description="Chain-of-thought statutory reasoning steps")

from app.services.langfuse_prompt_service import langfuse_prompt_service

# Prompts are fully migrated out of the codebase into Langfuse & decoupled registry.
# Dynamic resolution with local cache fallback:
def get_enterprise_system_prompt() -> str:
    return langfuse_prompt_service.get_prompt("policy-rag-subagent", label="live")

def get_few_shot_statutory_examples() -> str:
    return langfuse_prompt_service.get_prompt("leave-subagent", label="live")

def get_root_orchestrator_prompt() -> str:
    return langfuse_prompt_service.get_prompt("peopleops-root-orchestrator", label="live")

# Dynamic property aliases for backward compatibility
ENTERPRISE_SYSTEM_PROMPT = get_enterprise_system_prompt()
FEW_SHOT_STATUTORY_EXAMPLES = get_few_shot_statutory_examples()

def generate_statutory_cot_prompt(query: str, employee_context: str = "") -> str:
    """Combines System Mandates, Few-Shot Demonstrations, and Chain-of-Thought prompting."""
    return f"""{ENTERPRISE_SYSTEM_PROMPT}

{FEW_SHOT_STATUTORY_EXAMPLES}

[NEW EMPLOYEE QUERY]
Employee Context: {employee_context or 'Standard Employee (Maharashtra Establishment)'}
Query: {query}

Please formulate your assessment using step-by-step Chain-of-Thought:
1. Identify relevant statutory sections and company rules.
2. Calculate statutory entitlements and verify constraints (caps, expiration, overtime limits).
3. Check occupational health and medical certificate requirements.
4. Generate the final compliant recommendation.
"""
