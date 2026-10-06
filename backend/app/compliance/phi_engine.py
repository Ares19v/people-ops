"""Enterprise Regulatory Engine for HIPAA PHI, DPDP, and GDPR Redaction and De-Redaction."""

from dataclasses import dataclass
import threading
import time
from typing import Dict, List, Optional
from app.compliance.hipaa_rules import (
    ComplianceCategory,
    DetectedEntity,
    PATTERNS,
    NAME_PREFIX_PATTERN,
    CLINICAL_AND_HR_VERBS,
)

@dataclass
class RedactionResult:
    redacted_text: str
    original_text_length: int
    entities_detected: List[DetectedEntity]
    tokens_created: Dict[str, str]  # token -> original value
    session_id: str
    processing_time_ms: float

class TokenVault:
    """Thread-safe session-scoped storage for reversible pseudonymization tokens."""
    def __init__(self, ttl_seconds: int = 3600):
        self._vault: Dict[str, Dict[str, str]] = {}  # session_id -> {token: raw_value}
        self._timestamps: Dict[str, float] = {}
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()

    def store_tokens(self, session_id: str, tokens: Dict[str, str]):
        with self._lock:
            if session_id not in self._vault:
                self._vault[session_id] = {}
            self._vault[session_id].update(tokens)
            self._timestamps[session_id] = time.time()

    def get_tokens(self, session_id: str) -> Dict[str, str]:
        with self._lock:
            ts = self._timestamps.get(session_id)
            if ts and (time.time() - ts > self._ttl_seconds):
                self._vault.pop(session_id, None)
                self._timestamps.pop(session_id, None)
                return {}
            return self._vault.get(session_id, {}).copy()

    def clear_session(self, session_id: str):
        with self._lock:
            self._vault.pop(session_id, None)
            self._timestamps.pop(session_id, None)

class EnterpriseComplianceEngine:
    """Unified engine for DPDP 2023, GDPR, and HIPAA Safe Harbor 18."""

    def __init__(self, token_vault: Optional[TokenVault] = None):
        self.vault = token_vault or TokenVault()

    def identify_entities(self, text: str) -> List[DetectedEntity]:
        """Detects all sensitive PII and PHI entities."""
        entities: List[DetectedEntity] = []

        # 1. Regex rule scanning
        for category, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                val = match.group(1) if match.lastindex and match.group(1) else match.group(0)
                entities.append(
                    DetectedEntity(
                        category=category,
                        raw_value=val,
                        start=match.start(),
                        end=match.end(),
                        confidence=0.98 if category in [ComplianceCategory.AADHAAR, ComplianceCategory.PAN, ComplianceCategory.SSN] else 0.88,
                    )
                )

        # 2. Name context detection
        for match in NAME_PREFIX_PATTERN.finditer(text):
            if match.group(1):
                name_val = match.group(1).strip()
                words = [w.lower() for w in name_val.split()]
                if any(w in CLINICAL_AND_HR_VERBS for w in words):
                    continue
                start_offset = match.start(1)
                end_offset = match.end(1)
                entities.append(
                    DetectedEntity(
                        category=ComplianceCategory.NAME,
                        raw_value=name_val,
                        start=start_offset,
                        end=end_offset,
                        confidence=0.95,
                    )
                )

        # Sort descending by start index to avoid index shifting during replacement
        entities.sort(key=lambda e: e.start, reverse=True)
        return entities

    def redact(self, text: str, session_id: str) -> RedactionResult:
        """Tokenizes all identified PII/PHI into reversible surrogate tokens."""
        start_t = time.perf_counter()
        entities = self.identify_entities(text)

        cat_counters: Dict[ComplianceCategory, int] = {}
        tokens: Dict[str, str] = {}
        redacted = list(text)

        for entity in entities:
            cat_counters[entity.category] = cat_counters.get(entity.category, 0) + 1
            token = f"[{entity.category.value}_{cat_counters[entity.category]}]"
            entity.token_placeholder = token
            tokens[token] = entity.raw_value

            redacted[entity.start:entity.end] = list(token)

        final_redacted_text = "".join(redacted)

        if tokens:
            self.vault.store_tokens(session_id, tokens)

        elapsed = (time.perf_counter() - start_t) * 1000

        return RedactionResult(
            redacted_text=final_redacted_text,
            original_text_length=len(text),
            entities_detected=entities,
            tokens_created=tokens,
            session_id=session_id,
            processing_time_ms=round(elapsed, 2),
        )

    def de_redact(
        self,
        text: str,
        session_id: str,
        user_role: str = "HR_Manager",
        authorized_roles: Optional[List[str]] = None,
    ) -> str:
        """Restores surrogate tokens back to original plaintext values IF authorized."""
        if authorized_roles is None:
            # HR Managers, Admins, and Medical Officers can view real employee identity
            authorized_roles = ["Admin", "HR_Manager", "HR Manager", "Medical_Officer", "Doctor", "Clinician"]

        tokens = self.vault.get_tokens(session_id)
        if not tokens:
            return text

        is_authorized = user_role in authorized_roles
        output = text

        for token, raw_val in tokens.items():
            if is_authorized:
                output = output.replace(token, raw_val)
            else:
                # Masked format for unauthorized viewers
                cat = token.strip("[]").split("_")[0]
                if cat == "AADHAAR":
                    clean = raw_val.replace(" ", "").replace("-", "")
                    masked = f"XXXX-XXXX-{clean[-4:]}"
                elif cat == "PAN":
                    masked = f"{raw_val[:2]}XXXXXX{raw_val[-2:]}"
                else:
                    masked = f"***REDACTED_{token.strip('[]')}***"
                output = output.replace(token, masked)

        return output

compliance_engine = EnterpriseComplianceEngine()
