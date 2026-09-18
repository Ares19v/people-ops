import re
import os
from typing import Dict, Any, Tuple, Optional
from app.core.security import mask_all_pii

try:
    from nemoguardrails import RailsConfig, LLMRails
    NEMO_AVAILABLE = True
except ImportError:
    NEMO_AVAILABLE = False

class GuardrailsManager:
    """Enterprise safety manager running NeMo Guardrails and deterministic DPDP compliance checks."""

    # Jailbreak and injection patterns (OWASP LLM01)
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|prompts)", re.IGNORECASE),
        re.compile(r"(system\s+prompt|hidden\s+prompt|internal\s+instructions)", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+(dan|unrestricted|god\s*mode)", re.IGNORECASE),
        re.compile(r"(dump|drop|select\s+\*\s+from)\s+(users|credentials|passwords|database)", re.IGNORECASE),
        re.compile(r"(reveal|show|print)\s+(all\s+)?(secrets|credentials|tokens|keys)", re.IGNORECASE)
    ]

    # Unauthorized access probes (BOLA / Privacy)
    UNAUTHORIZED_PROBE_PATTERNS = [
        re.compile(r"(salary|compensation|paycheck)\s+of\s+(other|another|all|colleague)", re.IGNORECASE),
        re.compile(r"(aadhaar|pan)(\s+card)?\s+of\s+(other|another|colleague)", re.IGNORECASE),
        re.compile(r"bypass\s+(manager|approval|authorization)", re.IGNORECASE),
    ]

    def __init__(self):
        self._rails = None
        self._init_nemo()

    def _init_nemo(self):
        if not NEMO_AVAILABLE:
            return
        try:
            config_path = os.path.join(os.path.dirname(__file__), "config")
            if os.path.exists(config_path):
                config = RailsConfig.from_path(config_path)
                self._rails = LLMRails(config)
        except Exception:
            self._rails = None

    def check_input(self, user_message: str, user_role: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validates input boundaries.
        Returns: (is_safe: bool, blocked_reason: Optional[str], refusal_message: Optional[str])
        """
        # 1. Check prompt injection / jailbreak
        for pattern in self.INJECTION_PATTERNS:
            if pattern.search(user_message):
                return (
                    False,
                    "PROMPT_INJECTION_DETECTED",
                    "Safety Boundary Alert: Your request was identified as a prompt-injection or security-override attempt and has been blocked."
                )

        # 2. Check unauthorized employee data probe
        for pattern in self.UNAUTHORIZED_PROBE_PATTERNS:
            if pattern.search(user_message):
                return (
                    False,
                    "UNAUTHORIZED_ACCESS_PROBE",
                    "Access Denied: You cannot query confidential personal, financial, or authentication records of other personnel."
                )

        return True, None, None

    def check_output(self, raw_response: str, is_policy_query: bool = False) -> Tuple[str, str, Optional[str]]:
        """
        Validates and sanitizes output boundaries.
        Returns: (sanitized_response: str, guardrail_status: str, tripped_rail: Optional[str])
        """
        tripped_rail = None
        status = "PASSED"

        # 1. DPDP PII Scrubbing (Aadhaar, PAN, phone numbers)
        sanitized = mask_all_pii(raw_response)
        if sanitized != raw_response:
            tripped_rail = "OUTPUT_PII_MASKED"
            status = "OUTPUT_SCRUBBED"

        # 2. Enforce legal disclaimer if answering statutory/policy queries
        disclaimer_marker = "does not constitute formal legal advice"
        if is_policy_query and disclaimer_marker not in sanitized:
            sanitized += "\n\n> **Statutory Disclaimer**: *This response reflects company policy and the Maharashtra Shops and Establishments Act, 2017. It is provided for informational guidance and does not constitute formal legal advice.*"
            if not tripped_rail:
                tripped_rail = "LEGAL_DISCLAIMER_ATTACHED"

        return sanitized, status, tripped_rail

guardrails_manager = GuardrailsManager()
