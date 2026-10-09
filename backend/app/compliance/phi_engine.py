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

import os
import json
from app.core.security import encrypt_field, decrypt_field

class TokenVault:
    """Thread-safe persistent encrypted storage for reversible pseudonymization tokens."""
    def __init__(self, ttl_seconds: int = 3600):
        self._vault: Dict[str, Dict[str, str]] = {}  # session_id -> {token: raw_value}
        self._timestamps: Dict[str, float] = {}
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self._storage_dir = os.path.join(base_dir, "data", "token_vault")
        os.makedirs(self._storage_dir, exist_ok=True)

    def _get_vault_file(self, session_id: str) -> str:
        safe_sid = "".join(c for c in session_id if c.isalnum() or c in ("-", "_"))
        return os.path.join(self._storage_dir, f"{safe_sid}.vault")

    def store_tokens(self, session_id: str, tokens: Dict[str, str]):
        with self._lock:
            if session_id not in self._vault:
                self._vault[session_id] = {}
            self._vault[session_id].update(tokens)
            self._timestamps[session_id] = time.time()
            # Persist encrypted to disk
            try:
                vault_path = self._get_vault_file(session_id)
                payload_json = json.dumps({
                    "timestamp": self._timestamps[session_id],
                    "tokens": self._vault[session_id]
                })
                encrypted = encrypt_field(payload_json)
                with open(vault_path, "w", encoding="utf-8") as f:
                    f.write(encrypted)
            except Exception:
                pass

    def get_tokens(self, session_id: str) -> Dict[str, str]:
        with self._lock:
            ts = self._timestamps.get(session_id)
            if ts and (time.time() - ts > self._ttl_seconds):
                self._vault.pop(session_id, None)
                self._timestamps.pop(session_id, None)
                try:
                    os.remove(self._get_vault_file(session_id))
                except Exception:
                    pass
                return {}
            
            if session_id in self._vault:
                return self._vault[session_id].copy()
            
            # Attempt to restore from persistent encrypted vault on disk
            try:
                vault_path = self._get_vault_file(session_id)
                if os.path.exists(vault_path):
                    with open(vault_path, "r", encoding="utf-8") as f:
                        encrypted_str = f.read().strip()
                    decrypted_json = decrypt_field(encrypted_str)
                    data = json.loads(decrypted_json)
                    file_ts = data.get("timestamp", 0)
                    if time.time() - file_ts <= self._ttl_seconds:
                        self._vault[session_id] = data.get("tokens", {})
                        self._timestamps[session_id] = file_ts
                        return self._vault[session_id].copy()
            except Exception:
                pass
                
            return {}

    def clear_session(self, session_id: str):
        with self._lock:
            self._vault.pop(session_id, None)
            self._timestamps.pop(session_id, None)
            try:
                os.remove(self._get_vault_file(session_id))
            except Exception:
                pass

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
        user_role: str = "HR_MANAGER",
        authorized_roles: Optional[List[str]] = None,
    ) -> str:
        """Restores surrogate tokens back to original plaintext values IF authorized."""
        if authorized_roles is None:
            authorized_roles = [
                "ADMIN", "HR_MANAGER", "HR_ASSOCIATE", "MEDICAL_OFFICER"
            ]

        tokens = self.vault.get_tokens(session_id)
        if not tokens:
            return text

        normalized_user_role = str(user_role).upper().replace(" ", "_")
        normalized_authorized = {str(r).upper().replace(" ", "_") for r in authorized_roles}
        is_authorized = normalized_user_role in normalized_authorized
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
