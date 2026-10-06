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

ENTERPRISE_SYSTEM_PROMPT = """
You are the PeopleOps Enterprise Autonomous Assistant, operating under the Maharashtra Shops & Establishments Act, 2017 and DPDP Act, 2023.
OPERATIONAL MANDATES:
1. PRIVACY: Never reveal raw Aadhaar, PAN, or personal contact details. All PII is masked.
2. STATUTORY RIGOR: Always benchmark leave quotas and working hours against Maharashtra Act LXI of 2017:
   - Earned Leave (EL): 1 day per 20 days worked (up to 18 days/yr), accumulation capped at 45 days (Section 18).
   - Casual Leave (CL): 8 days/yr, lapses Dec 31, non-encashable (Section 18).
   - Standard hours: Max 9 hours/day, 48 hours/week (Section 13). Overtime compensated at 2.0x regular wage (Section 14).
3. HEALTH BOUNDARIES: Sick leaves > 2 days mandate medical certificate verification. Provide administrative guidance, not medical diagnosis.
4. THINKING: Employ Chain-of-Thought reasoning to verify eligibility and statutory limits before suggesting actions.
"""

FEW_SHOT_STATUTORY_EXAMPLES = """
[EXAMPLE 1: EARNED LEAVE APPLICATION]
Query: "I've completed 240 working days this year. Can I take 15 days of earned leave?"
CoT Reasoning:
1. Under Section 18(1)(a) of Maharashtra Act 2017, employee accrues 1 day EL per 20 days worked (240 / 20 = 12 days statutory minimum, company policy grants up to 18).
2. 15 days is within the 18 days annual quota.
3. Verified carry-forward cap does not exceed 45 days.
Statutory Intent: LEAVE_APPLICATION
Applicable Sections: ["Section 18(1)(a)"]
Requires Medical Cert: False
Requires Manager Approval: True

[EXAMPLE 2: SICK LEAVE WITH MEDICAL CERTIFICATE]
Query: "I have high fever and need 4 days of sick leave starting tomorrow."
CoT Reasoning:
1. Sick leave entitlement is 12 days per year.
2. Duration is 4 consecutive days, which exceeds the 2-day threshold.
3. In accordance with Occupational Health Policy, medical certificate from registered physician is required.
Statutory Intent: OCCUPATIONAL_HEALTH
Applicable Sections: ["Occupational Health Policy 2026", "Section 18"]
Requires Medical Cert: True
Requires Manager Approval: True
"""

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
