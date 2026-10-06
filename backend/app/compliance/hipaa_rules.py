"""Regulatory Identifiers and Detection Rules for HIPAA Safe Harbor 18, GDPR, and DPDP Act 2023."""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Dict, List, Optional, Pattern

class ComplianceCategory(str, Enum):
    # HIPAA Safe Harbor 18
    NAME = "NAME"
    GEOGRAPHIC = "GEOGRAPHIC"
    DATE = "DATE"
    PHONE = "PHONE"
    FAX = "FAX"
    EMAIL = "EMAIL"
    SSN = "SSN"
    MRN = "MRN"
    HEALTH_PLAN_ID = "HEALTH_PLAN_ID"
    ACCOUNT_NUMBER = "ACCOUNT_NUMBER"
    CERTIFICATE_LICENSE = "CERTIFICATE_LICENSE"
    VEHICLE_ID = "VEHICLE_ID"
    DEVICE_ID = "DEVICE_ID"
    URL = "URL"
    IP_ADDRESS = "IP_ADDRESS"
    BIOMETRIC_ID = "BIOMETRIC_ID"
    PHOTO_ID = "PHOTO_ID"
    UNIQUE_ID = "UNIQUE_ID"

    # DPDP Act 2023 (India)
    AADHAAR = "AADHAAR"
    PAN = "PAN"

@dataclass
class DetectedEntity:
    category: ComplianceCategory
    raw_value: str
    start: int
    end: int
    confidence: float
    token_placeholder: Optional[str] = None

# Compiled regex patterns
PATTERNS: Dict[ComplianceCategory, Pattern[str]] = {
    ComplianceCategory.AADHAAR: re.compile(
        r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b"
    ),
    ComplianceCategory.PAN: re.compile(
        r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b"
    ),
    ComplianceCategory.SSN: re.compile(
        r"\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b"
    ),
    ComplianceCategory.MRN: re.compile(
        r"\b(?:MRN|Medical\s*Record\s*(?:Number|#|No\.?))[:\s#]*([A-Z0-9]{6,12})\b|\bMRN-([A-Z0-9]{6,10})\b",
        re.IGNORECASE,
    ),
    ComplianceCategory.EMAIL: re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
    ),
    ComplianceCategory.PHONE: re.compile(
        r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b|\b(?:\+91|91|0)?[6-9]\d{9}\b"
    ),
    ComplianceCategory.DATE: re.compile(
        r"\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b",
        re.IGNORECASE,
    ),
    ComplianceCategory.HEALTH_PLAN_ID: re.compile(
        r"\b(?:Health\s*Plan|Policy|Ins(?:urance)?|Member|Beneficiary)\s*(?:ID|#|No\.?)[:\s#\-]*([A-Z0-9\-]{8,16})\b",
        re.IGNORECASE,
    ),
    ComplianceCategory.IP_ADDRESS: re.compile(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    ),
}

CLINICAL_AND_HR_VERBS = {
    "take", "takes", "taking", "applied", "apply", "applying", "requested",
    "request", "reports", "reported", "admitted", "approved", "rejected",
    "has", "had", "was", "is", "denies", "asking", "presenting", "presented"
}

NAME_PREFIX_PATTERN = re.compile(
    r"\b(?:Patient(?:\s*Name)?|Employee(?:\s*Name)?|Candidate|Pt\.?|Name)[:\s\-]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b"
)
