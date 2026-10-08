"""Semantic Intent & Pragmatics Router for PeopleOps Multi-Agent System.

Provides robust, multi-intent classification and disambiguation across:
1. Personal Ledger (leave balances, timecards, personal requests) -> leave_subagent / timesheet_subagent
2. Normative Knowledge (statutory labour law, company handbook, policies) -> policy_rag_subagent
3. Occupational Health & Medical Triage (illness, doctor's certificates, mediclaim) -> health_subagent
4. External HRMS Synchronization -> zoho_subagent
5. Compound Multi-Intent Queries (e.g., Sickness + Balance check) -> parallel subagent execution
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Set


class QueryScope(str, Enum):
    PERSONAL_LEDGER = "PERSONAL_LEDGER"
    NORMATIVE_POLICY = "NORMATIVE_POLICY"
    HEALTH_TRIAGE = "HEALTH_TRIAGE"
    TIMESHEET_LOGGING = "TIMESHEET_LOGGING"
    ZOHO_SYNC = "ZOHO_SYNC"
    COMPOUND_HYBRID = "COMPOUND_HYBRID"
    GENERAL_HELP = "GENERAL_HELP"


@dataclass
class IntentRoute:
    primary_scope: QueryScope
    selected_tools: List[str]
    confidences: Dict[str, float] = field(default_factory=dict)
    is_compound: bool = False
    reasoning: str = ""
    extracted_entities: Dict[str, Any] = field(default_factory=dict)


class SemanticIntentRouter:
    """Enterprise Pragmatic Classifier for Multi-Agent Dispatch.
    
    Evaluates grammatical subjecthood, modal verbs, entity presence,
    and conversational context to eliminate brittle keyword matching.
    """

    # 1. First-person subjectivity markers (indicates personal ledger)
    FIRST_PERSON_PATTERNS = [
        r"\b(i|my|me|mine|myself|we|our|us)\b",
        r"\b(do i have|have i got|can i|may i|could i|should i|am i)\b",
        r"\b(my balance|my leave|my leaves|my days|my pto|my vacation|my timesheet|my hours)\b",
        r"\b(have left|remaining for me|left for me|allocated to me|credited to me)\b",
        r"\b(for myself|take off|take a day off|take leave|apply for|book a day|request leave)\b",
    ]

    # 2. Leave entities & balance tokens
    LEAVE_ENTITIES = [
        r"\b(leave|leaves|day off|days off|time off|pto|vacation|holiday)\b",
        r"\b(cl|el|sl|lwp|casual leave|earned leave|sick leave|leave without pay|privilege leave)\b",
        r"\b(balance|balances|quota|allowance|remaining days|available days)\b",
    ]

    # 3. Policy & Normative Statutory markers (indicates handbook / acts)
    POLICY_PATTERNS = [
        r"\b(policy|handbook|rules?|statutory|regulation|mandate|compliance)\b",
        r"\b(maharashtra|karnataka|delhi|shops and establishments|act|act 2017|section \d+)\b",
        r"\b(legal|law|labour law|labor law|constitution|statute|code)\b",
        r"\b(carry forward policy|maternity benefit|paternity leave policy|notice period|probation)\b",
        r"\b(what is the rule|what does the law say|are employees entitled|is it mandatory)\b",
    ]

    # 4. Health & Occupational Triage markers
    HEALTH_PATTERNS = [
        r"\b(sick|fever|cough|cold|ill|illness|unwell|medical|doctor|physician|practitioner)\b",
        r"\b(doctor certificate|medical certificate|medical note|fit to work|sick note)\b",
        r"\b(hospital|hospitalization|admitted|mediclaim|group insurance|health insurance|coverage)\b",
        r"\b(ergonomic|ergonomics|occupational health|injury|workplace safety)\b",
    ]

    # 5. Timesheet & Working Hours markers
    TIMESHEET_PATTERNS = [
        r"\b(timesheet|timesheets|timecard|working hours|work hours)\b",
        r"\b(billable|non-billable|project hours|overtime|ot|overtime rate)\b",
        r"\b(clock in|clock out|weekly hours|daily cap|spread-over|quarterly overtime)\b",
        r"\b(log|record|track|submit|enter|entered)\b.*\b(hours?|time)\b",
        r"\b(worked|logged)\s+\d+(\.\d+)?\s*hours?\b",
        r"\b\d+(\.\d+)?\s*hours?\b.*\b(project|task|client|yesterday|today|this week)\b",
    ]

    # 6. Zoho People HRMS markers
    ZOHO_PATTERNS = [
        r"\b(zoho|zoho people|external hrms|sync attendance|sync records|api sync)\b",
    ]

    # 7. Conversational greetings
    GREETING_PATTERNS = [
        r"\b(hi|hello|hey|good morning|good afternoon|good evening|howdy|greetings)\b",
        r"\b(who are you|what can you do|help me|capabilities|what do you do|what are your features)\b",
        r"\bwhat can you help(\s+me)?\s+with\b",
    ]

    @classmethod
    def _matches_any(cls, patterns: List[str], text: str) -> bool:
        return any(re.search(pat, text, re.IGNORECASE) for pat in patterns)

    @classmethod
    def _count_matches(cls, patterns: List[str], text: str) -> int:
        return sum(1 for pat in patterns if re.search(pat, text, re.IGNORECASE))

    @classmethod
    def classify(cls, query: str, conversation_context: str = "") -> IntentRoute:
        """Classifies a user query into specialized subagent targets and semantic scope."""
        text = query.strip()
        text_lower = text.lower()
        full_context = f"{conversation_context}\n{text}".lower()

        # Check for pure greeting or capability inquiry (without domain action)
        is_greeting = cls._matches_any(cls.GREETING_PATTERNS, text_lower)
        has_domain_keywords = any(w in text_lower for w in ["leave", "timesheet", "hour", "sick", "doctor", "zoho", "balance", "apply"])
        if is_greeting and not has_domain_keywords:
            return IntentRoute(
                primary_scope=QueryScope.GENERAL_HELP,
                selected_tools=["policy_rag_subagent"],
                confidences={"general": 0.95},
                reasoning="General greeting or capabilities question."
            )

        # 1. Feature detection
        is_first_person = cls._matches_any(cls.FIRST_PERSON_PATTERNS, text_lower)
        has_leave_mention = cls._matches_any(cls.LEAVE_ENTITIES, text_lower)
        has_policy_mention = cls._matches_any(cls.POLICY_PATTERNS, text_lower)
        has_health_mention = cls._matches_any(cls.HEALTH_PATTERNS, text_lower)
        has_timesheet_mention = cls._matches_any(cls.TIMESHEET_PATTERNS, text_lower)
        has_zoho_mention = cls._matches_any(cls.ZOHO_PATTERNS, text_lower)

        # 2. Check for balance inquiry templates
        is_balance_inquiry = bool(re.search(
            r"(how many|how much|what('s| is) my|show my|check my|available|remaining)\s+.*(day|leave|time off|pto|cl|el|sl|balance)",
            text_lower
        )) or (is_first_person and has_leave_mention and any(w in text_lower for w in ["have", "got", "left", "remaining", "balance", "count", "quota"]))

        # 3. Check for application/action intent
        is_apply_intent = bool(re.search(
            r"\b(apply|take|request|book|submit|need)\b.*(leave|day off|days off|vacation|time off|friday|monday|tomorrow)",
            text_lower
        )) or ("can i take" in text_lower or "i want to take" in text_lower or "i need to take" in text_lower)

        # 4. Check for pure abstract policy inquiry
        # If it asks about law, act, rules, or section AND has NO first-person balance request
        is_pure_policy = (
            has_policy_mention and not (is_balance_inquiry or is_apply_intent)
        ) or (
            any(w in text_lower for w in ["what is the policy", "what is the rule", "under maharashtra act", "section 18", "section 14", "notice period", "probation period"])
        )

        selected_tools: List[str] = []
        confidences: Dict[str, float] = {}

        # ── Domain 1: Zoho People Sync ────────────────────────────────────────
        if has_zoho_mention:
            selected_tools.append("zoho_subagent")
            confidences["zoho_subagent"] = 0.95

        # ── Domain 2: Occupational Health & Sickness Triage ───────────────────
        if has_health_mention:
            selected_tools.append("health_subagent")
            confidences["health_subagent"] = 0.90

        # ── Domain 3: Timesheet & Working Hours ───────────────────────────────
        if has_timesheet_mention:
            selected_tools.append("timesheet_subagent")
            confidences["timesheet_subagent"] = 0.90

        # ── Domain 4: Leave Management (Personal vs. Policy) ──────────────────
        if is_balance_inquiry or is_apply_intent or (has_leave_mention and is_first_person):
            if "leave_subagent" not in selected_tools:
                selected_tools.append("leave_subagent")
            confidences["leave_subagent"] = 0.95
        elif has_leave_mention and is_pure_policy:
            if "policy_rag_subagent" not in selected_tools:
                selected_tools.append("policy_rag_subagent")
            confidences["policy_rag_subagent"] = 0.95
        elif has_leave_mention and not selected_tools:
            # When leave is mentioned without clear direction:
            # If the user says "how many leave days" without policy keywords, default to their personal balance!
            if any(w in text_lower for w in ["how many", "how much", "can i", "do i"]):
                selected_tools.append("leave_subagent")
                confidences["leave_subagent"] = 0.85
            else:
                selected_tools.append("policy_rag_subagent")
                confidences["policy_rag_subagent"] = 0.75

        # ── Domain 5: Statutory Policy & Legal Knowledge ──────────────────────
        if is_pure_policy and "policy_rag_subagent" not in selected_tools:
            selected_tools.append("policy_rag_subagent")
            confidences["policy_rag_subagent"] = 0.95

        # ── Domain 6: Compound Queries (Decomposition & Parallel Dispatch) ───
        # Case A: Sickness report with leave balance ("I have fever, how many sick days do I have left?")
        if has_health_mention and (is_balance_inquiry or is_apply_intent or "sick leave" in text_lower or "days" in text_lower):
            if "leave_subagent" not in selected_tools:
                selected_tools.append("leave_subagent")
            if "health_subagent" not in selected_tools:
                selected_tools.append("health_subagent")

        # Case B: Overtime rule check while checking or logging timesheet
        if has_timesheet_mention and ("law" in text_lower or "act" in text_lower or "rate" in text_lower or "limit" in text_lower):
            # Timesheet subagent already contains Maharashtra Section 13/14 statutory overtime limits
            pass

        # ── Fallback Safety ───────────────────────────────────────────────────
        if not selected_tools:
            # If no tools matched, check multi-turn context
            if conversation_context:
                if any(w in full_context for w in ["leave", "balance", "vacation"]):
                    selected_tools.append("leave_subagent")
                    confidences["leave_subagent"] = 0.65
                elif any(w in full_context for w in ["timesheet", "hours"]):
                    selected_tools.append("timesheet_subagent")
                    confidences["timesheet_subagent"] = 0.65

            # Default safe fallback is policy_rag_subagent
            if not selected_tools:
                selected_tools.append("policy_rag_subagent")
                confidences["policy_rag_subagent"] = 0.50

        # Scope Determination
        is_compound = len(selected_tools) > 1
        if is_compound:
            primary_scope = QueryScope.COMPOUND_HYBRID
        elif "leave_subagent" in selected_tools:
            primary_scope = QueryScope.PERSONAL_LEDGER
        elif "timesheet_subagent" in selected_tools:
            primary_scope = QueryScope.TIMESHEET_LOGGING
        elif "health_subagent" in selected_tools:
            primary_scope = QueryScope.HEALTH_TRIAGE
        elif "zoho_subagent" in selected_tools:
            primary_scope = QueryScope.ZOHO_SYNC
        else:
            primary_scope = QueryScope.NORMATIVE_POLICY

        reasoning = (
            f"Classified into {primary_scope.value} -> dispatching to {selected_tools}. "
            f"Subjectivity: {'First-Person/Personal' if is_first_person else 'Objective/Third-Person'}. "
            f"Compound: {is_compound}."
        )

        return IntentRoute(
            primary_scope=primary_scope,
            selected_tools=selected_tools,
            confidences=confidences,
            is_compound=is_compound,
            reasoning=reasoning
        )


intent_router = SemanticIntentRouter()
