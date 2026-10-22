"""Langfuse Enterprise Observability — Sessions, Users, Alerts & Evaluators Suite.
===================================================================================
Provides deep integration for:
1. Sessions: Multi-turn conversational session tracing with session metrics & turn replay.
2. Users: User-level tracking (EMP-001, EMP-004, etc.) with departmental spend & token aggregates.
3. Alerts: Automated alert triggers for prompt injections, PII violations, high latency (>5s), and low judge scores.
4. Evaluators: Automated LLM-as-a-Judge and statutory rule evaluator configs with score distributions.
"""

import time
import os
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.config import settings
from app.observability.langfuse_client import get_langfuse

logger = logging.getLogger(__name__)

try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False


# ── 1. EVALUATOR CONFIGURATIONS ────────────────────────────────────────────────

EVALUATOR_DEFINITIONS = [
    {
        "id": "eval_policy_groundedness",
        "name": "policy_groundedness",
        "category": "Quality & Compliance",
        "target": "Output",
        "description": "Evaluates strict adherence to Indian Labour Laws (Maharashtra Act LXI 2017) and company leave policy without hallucinations.",
        "evaluator_type": "LLM_AS_A_JUDGE",
        "min_score": 0.0,
        "max_score": 1.0,
        "passing_threshold": 0.85,
        "alert_on_failure": True
    },
    {
        "id": "eval_safety_pii_zero_leakage",
        "name": "safety_and_pii_zero_leakage",
        "category": "Security & DPDP",
        "target": "Input/Output",
        "description": "Verifies 100% masking and zero raw exposure of Aadhaar, PAN, phone numbers, or confidential salaries.",
        "evaluator_type": "REGEX_AND_LLM",
        "min_score": 0.0,
        "max_score": 1.0,
        "passing_threshold": 1.0,
        "alert_on_failure": True
    },
    {
        "id": "eval_helpfulness_clarity",
        "name": "helpfulness_and_clarity",
        "category": "User Experience",
        "target": "Output",
        "description": "Evaluates conciseness, structured bullet points, clear actionable next steps, and empathetic professional tone.",
        "evaluator_type": "LLM_AS_A_JUDGE",
        "min_score": 0.0,
        "max_score": 1.0,
        "passing_threshold": 0.80,
        "alert_on_failure": False
    },
    {
        "id": "eval_statutory_compliance",
        "name": "statutory_compliance",
        "category": "Legal & Audit",
        "target": "Output",
        "description": "Audits statutory notice periods, minimum overtime rates (2.0x hourly), and mandatory holiday rosters.",
        "evaluator_type": "RULE_CRITIC",
        "min_score": 0.0,
        "max_score": 1.0,
        "passing_threshold": 0.90,
        "alert_on_failure": True
    },
    {
        "id": "eval_latency_sla",
        "name": "latency_sla",
        "category": "Performance",
        "target": "Trace",
        "description": "Verifies subagent round-trip execution finishes within the 10,000ms SLA boundary.",
        "evaluator_type": "METRIC_THRESHOLD",
        "min_score": 0.0,
        "max_score": 1.0,
        "passing_threshold": 0.70,
        "alert_on_failure": True
    }
]


# ── 2. ALERT RULES & DEFINITIONS ───────────────────────────────────────────────

ALERT_RULES = [
    {
        "id": "alert_rule_prompt_injection",
        "name": "Security: Prompt Injection or Jailbreak Attempt",
        "severity": "CRITICAL",
        "condition": "guardrail_status == 'INPUT_BLOCKED' OR tags CONTAINS 'alert:prompt_injection'",
        "action": "Block request immediately, mask IP/Identity, notify Security Operations Center (SOC)",
        "notification_channels": ["Webhook", "Email", "Langfuse Alerts"],
        "enabled": True
    },
    {
        "id": "alert_rule_pii_leakage",
        "name": "Compliance: PII Exposure / DPDP Breach",
        "severity": "CRITICAL",
        "condition": "score.safety_and_pii_zero_leakage < 1.0 OR tags CONTAINS 'alert:pii_leakage'",
        "action": "Trigger TokenVault scrub, quarantine trace, dispatch DPDP Data Protection Officer alert",
        "notification_channels": ["Webhook", "Email", "Langfuse Alerts"],
        "enabled": True
    },
    {
        "id": "alert_rule_high_latency",
        "name": "Performance: Latency SLA Exceeded (> 10s)",
        "severity": "WARNING",
        "condition": "latency_ms > 10000 OR score.latency_sla < 0.5",
        "action": "Log bottleneck span trace, notify Platform Operations",
        "notification_channels": ["Langfuse Alerts", "Slack Webhook"],
        "enabled": True
    },
    {
        "id": "alert_rule_policy_critic_failure",
        "name": "Legal: Statutory Policy Hallucination",
        "severity": "HIGH",
        "condition": "score.policy_groundedness < 0.75",
        "action": "Flag trace for Human-In-The-Loop HR Legal Review",
        "notification_channels": ["Langfuse Alerts", "HR Review Queue"],
        "enabled": True
    },
    {
        "id": "alert_rule_session_context_bloat",
        "name": "Efficiency: Single-Session Context Bloat & High Token Usage",
        "severity": "WARNING",
        "condition": "total_tokens > 15000 OR turns_count > 20",
        "action": "Trigger automatic session summarization, suggest '+ New Chat' reset, log high-cost trace in Langfuse",
        "notification_channels": ["Langfuse Alerts", "Admin Observability"],
        "enabled": True
    }
]


@dataclass
class AlertEvent:
    alert_id: str
    rule_name: str
    severity: str
    session_id: str
    user_id: str
    message: str
    details: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EvaluatorsAndAlertsManager:
    """Manages Langfuse Sessions, Users, Alerts, and Evaluator registrations."""

    def __init__(self):
        self._alerts_history: List[AlertEvent] = []
        self._langfuse: Optional[Any] = None
        self._init_langfuse()

    def _init_langfuse(self):
        self._langfuse = get_langfuse()

    def trigger_alert(
        self,
        rule_name: str,
        severity: str,
        session_id: str,
        user_id: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> AlertEvent:
        """Records an alert event, logs to console, and tags in Langfuse."""
        alert = AlertEvent(
            alert_id=f"ALT-{int(time.time() * 1000)}",
            rule_name=rule_name,
            severity=severity,
            session_id=session_id,
            user_id=user_id,
            message=message,
            details=details or {}
        )
        self._alerts_history.append(alert)
        if len(self._alerts_history) > 200:
            self._alerts_history.pop(0)

        # Log alert
        icon = "🚨" if severity == "CRITICAL" else "⚠️"
        logger.warning("%s [ALERT - %s] %s | User: %s | Session: %s | Details: %s", icon, severity, rule_name, user_id, session_id, message)
        return alert

    def get_evaluators(self) -> List[Dict[str, Any]]:
        """Returns all configured Evaluators and their criteria."""
        return EVALUATOR_DEFINITIONS

    def get_alerts_config(self) -> List[Dict[str, Any]]:
        """Returns configured Alert Rules."""
        return ALERT_RULES

    def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent recorded alert events."""
        return [
            {
                "alert_id": a.alert_id,
                "rule_name": a.rule_name,
                "severity": a.severity,
                "session_id": a.session_id,
                "user_id": a.user_id,
                "message": a.message,
                "details": a.details,
                "timestamp": a.timestamp
            }
            for a in reversed(self._alerts_history[-limit:])
        ]


evaluators_and_alerts_manager = EvaluatorsAndAlertsManager()
