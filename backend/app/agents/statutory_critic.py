"""Statutory Reflection & Verification Critic Agent.

Performs dual-pass verification on subagent and LLM outputs, validating citations
against jurisdiction labor laws dynamically via StatutoryRuleEngine.
"""

from dataclasses import dataclass, field
import re
import time
from typing import Dict, List, Optional, Tuple
from app.compliance.statutory_rules import statutory_rules, JurisdictionRuleSet

@dataclass
class StatutoryVerificationResult:
    is_valid: bool
    critique_notes: List[str]
    corrected_text: str
    statutory_citations: List[str]
    corrections_applied: int
    duration_ms: float
    jurisdiction_applied: str

class StatutoryCriticAgent:
    """Verifies that legal numbers, multipliers, and statutory clauses are strictly accurate across jurisdictions."""

    def _build_rules_for_jurisdiction(self, rule_set: JurisdictionRuleSet) -> List[Dict]:
        return [
            {
                "id": f"{rule_set.jurisdiction_code}_OVERTIME_RATE",
                "section": f"{rule_set.statutory_sections.get('overtime', 'Overtime Section')}",
                "description": f"Overtime must be calculated at {rule_set.overtime_multiplier}x the ordinary rate.",
                "hallucination_pattern": re.compile(r"\b(1\.5[xX]|150%|time\s+and\s+a\s+half|1\.25[xX])\s*(?:for\s+overtime|overtime\s+rate|multiplier)?\b", re.IGNORECASE),
                "correct_claim": f"twice the ordinary rate of wages ({rule_set.overtime_multiplier}x)",
                "mandatory_clause": f"{rule_set.statutory_sections.get('overtime', 'Overtime Section')} of the {rule_set.governing_act}"
            },
            {
                "id": f"{rule_set.jurisdiction_code}_OVERTIME_QUARTER_CAP",
                "section": f"{rule_set.statutory_sections.get('overtime', 'Overtime Section')}",
                "description": f"Total overtime hours cannot exceed {rule_set.overtime_quarterly_cap_hours} hours per quarter.",
                "hallucination_pattern": re.compile(r"\b(?:overtime\s+limit|cap)\s+(?:is|of)\s+(?:50|60|100|150|200)\s+hours\b", re.IGNORECASE),
                "correct_claim": f"maximum of {rule_set.overtime_quarterly_cap_hours} hours per quarter",
                "mandatory_clause": f"{rule_set.governing_act} statutory quarterly overtime ceiling"
            },
            {
                "id": f"{rule_set.jurisdiction_code}_DAILY_HOURS_CAP",
                "section": f"{rule_set.statutory_sections.get('daily_hours', 'Daily Hours Section')}",
                "description": f"Daily working hours shall not exceed {int(rule_set.standard_daily_hours)} hours in any day.",
                "hallucination_pattern": re.compile(r"\b(?:maximum|daily)\s+hours?\s+(?:is|limit|cap)\s+(?:10|11|12)\s+hours\b", re.IGNORECASE),
                "correct_claim": f"{int(rule_set.standard_daily_hours)} hours per day (excluding overtime)",
                "mandatory_clause": f"{rule_set.statutory_sections.get('daily_hours', 'Daily Hours Section')} daily work duration limitation"
            },
            {
                "id": f"{rule_set.jurisdiction_code}_EARNED_LEAVE_ACCUMULATION",
                "section": f"{rule_set.statutory_sections.get('leave_with_pay', 'Leave Section')}",
                "description": f"Earned Leave accumulation is capped at {rule_set.earned_leave_carry_forward_max} days.",
                "hallucination_pattern": re.compile(r"\b(?:carry\s*forward|accumulat\w+)\s+(?:up\s+to\s+)?(?:30|60|90|unlimited)\s+days?\b", re.IGNORECASE),
                "correct_claim": f"maximum carry-forward accumulation of {rule_set.earned_leave_carry_forward_max} days",
                "mandatory_clause": f"{rule_set.statutory_sections.get('leave_with_pay', 'Leave Section')} Earned Leave statutory accumulation cap"
            },
            {
                "id": f"{rule_set.jurisdiction_code}_CASUAL_LEAVE_ENTITLEMENT",
                "section": f"{rule_set.statutory_sections.get('leave_with_pay', 'Leave Section')}",
                "description": f"Casual Leave entitlement is {rule_set.casual_leave_annual_days} days.",
                "hallucination_pattern": re.compile(r"\b(?:casual\s+leave|CL)\s+(?:of|is|entitlement)\s+(?:10|12|14|15)\s+days?\b", re.IGNORECASE),
                "correct_claim": f"{rule_set.casual_leave_annual_days} days Casual Leave per calendar year",
                "mandatory_clause": f"{rule_set.statutory_sections.get('leave_with_pay', 'Leave Section')} Casual Leave entitlement"
            }
        ]

    def verify_and_correct(self, text: str, user_query: str = "", jurisdiction: Optional[str] = None) -> StatutoryVerificationResult:
        """Inspects the draft response for legal miscitations and self-corrects them."""
        start_t = time.perf_counter()
        rule_set = statutory_rules.get_rules(jurisdiction)
        rules = self._build_rules_for_jurisdiction(rule_set)

        corrected_text = text
        critique_notes: List[str] = []
        citations_found: List[str] = []
        corrections_count = 0

        for rule in rules:
            match = rule["hallucination_pattern"].search(corrected_text)
            if match:
                critique_notes.append(
                    f"Corrected statutory miscitation ({rule['section']}): Replaced '{match.group(0)}' with '{rule['correct_claim']}'."
                )
                corrected_text = rule["hallucination_pattern"].sub(
                    f"{rule['correct_claim']} (pursuant to {rule['mandatory_clause']})",
                    corrected_text
                )
                corrections_count += 1
                citations_found.append(rule["section"])

        # Check if text mentions Maharashtra law without citing the Act year
        if "maharashtra" in corrected_text.lower() and "2017" not in corrected_text:
            corrected_text = re.sub(
                r"\bMaharashtra\s+(?:Act|Shops\s+and\s+Establishments\s+Act)\b",
                "Maharashtra Shops and Establishments (Regulation of Employment and Conditions of Service) Act, 2017",
                corrected_text,
                flags=re.IGNORECASE
            )

        elapsed = (time.perf_counter() - start_t) * 1000

        return StatutoryVerificationResult(
            is_valid=(corrections_count == 0),
            critique_notes=critique_notes,
            corrected_text=corrected_text,
            statutory_citations=citations_found,
            corrections_applied=corrections_count,
            duration_ms=round(elapsed, 2),
            jurisdiction_applied=rule_set.state_name
        )

    async def critique_with_llm(
        self, text: str, user_query: str = "", jurisdiction: Optional[str] = None
    ) -> StatutoryVerificationResult:
        """Dual-pass statutory verification: LLM self-reflection when active, grounded by statutory rules."""
        from app.core.llm_bridge import resolve_llm_provider, generate_summary
        draft = text
        if resolve_llm_provider() != "mock":
            critic_prompt = (
                f"You are a Statutory Labour Law Critic. Audit this HR response for statutory accuracy:\n\n"
                f"Query: {user_query}\n"
                f"Draft: {text}\n\n"
                f"Statutory invariants: Max 9h daily standard hours (Sec 13), Overtime at 2.0x (Sec 14), "
                f"Earned Leave accumulation capped at 45 days (Sec 18), Casual Leave 8 days. "
                f"Output the corrected response if any statutory clauses are inaccurate."
            )
            try:
                reflection = await generate_summary(critic_prompt)
                if reflection and len(reflection) > 30 and not reflection.startswith("[MOCK"):
                    draft = reflection
            except Exception:
                pass
        return self.verify_and_correct(draft, user_query=user_query, jurisdiction=jurisdiction)

statutory_critic = StatutoryCriticAgent()
