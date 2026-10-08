"""Multi-Jurisdiction Statutory Labor Law Registry.

Externalizes hardcoded state labour laws into configurable jurisdiction rule sets
supporting Maharashtra, Karnataka, Delhi, and National Model Shops & Establishments Acts.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional
from app.core.config import settings

class StatutoryJurisdiction(str, Enum):
    MAHARASHTRA = "MAHARASHTRA"
    KARNATAKA = "KARNATAKA"
    DELHI = "DELHI"
    CENTRAL_MODEL = "CENTRAL_MODEL"

@dataclass
class JurisdictionRuleSet:
    jurisdiction_code: StatutoryJurisdiction
    state_name: str
    governing_act: str
    standard_daily_hours: float
    standard_weekly_hours: float
    overtime_multiplier: float
    overtime_quarterly_cap_hours: int
    daily_spreadover_cap_hours: float
    earned_leave_carry_forward_max: int
    casual_leave_annual_days: int
    medical_cert_threshold_days: int
    statutory_sections: Dict[str, str] = field(default_factory=dict)

JURISDICTION_REGISTRY: Dict[StatutoryJurisdiction, JurisdictionRuleSet] = {
    StatutoryJurisdiction.MAHARASHTRA: JurisdictionRuleSet(
        jurisdiction_code=StatutoryJurisdiction.MAHARASHTRA,
        state_name="Maharashtra",
        governing_act="Maharashtra Shops and Establishments (Regulation of Employment and Conditions of Service) Act, 2017",
        standard_daily_hours=9.0,
        standard_weekly_hours=48.0,
        overtime_multiplier=2.0,
        overtime_quarterly_cap_hours=125,
        daily_spreadover_cap_hours=10.5,
        earned_leave_carry_forward_max=45,
        casual_leave_annual_days=8,
        medical_cert_threshold_days=2,
        statutory_sections={
            "overtime": "Section 14",
            "daily_hours": "Section 13",
            "leave_with_pay": "Section 18",
            "rest_interval": "Section 15"
        }
    ),
    StatutoryJurisdiction.KARNATAKA: JurisdictionRuleSet(
        jurisdiction_code=StatutoryJurisdiction.KARNATAKA,
        state_name="Karnataka",
        governing_act="Karnataka Shops and Commercial Establishments Act, 1961",
        standard_daily_hours=9.0,
        standard_weekly_hours=48.0,
        overtime_multiplier=2.0,
        overtime_quarterly_cap_hours=50,  # Karnataka quarterly OT cap
        daily_spreadover_cap_hours=12.0,
        earned_leave_carry_forward_max=30,  # Karnataka carry-forward cap
        casual_leave_annual_days=12,
        medical_cert_threshold_days=3,
        statutory_sections={
            "overtime": "Section 8",
            "daily_hours": "Section 7",
            "leave_with_pay": "Section 15",
            "rest_interval": "Section 9"
        }
    ),
    StatutoryJurisdiction.DELHI: JurisdictionRuleSet(
        jurisdiction_code=StatutoryJurisdiction.DELHI,
        state_name="Delhi",
        governing_act="Delhi Shops and Establishments Act, 1954",
        standard_daily_hours=9.0,
        standard_weekly_hours=48.0,
        overtime_multiplier=2.0,
        overtime_quarterly_cap_hours=54,
        daily_spreadover_cap_hours=10.5,
        earned_leave_carry_forward_max=45,
        casual_leave_annual_days=12,
        medical_cert_threshold_days=2,
        statutory_sections={
            "overtime": "Section 13",
            "daily_hours": "Section 8",
            "leave_with_pay": "Section 22",
            "rest_interval": "Section 10"
        }
    )
}

class StatutoryRuleEngine:
    """Provides jurisdictional rules based on employee location or company default."""

    @staticmethod
    def get_rules(jurisdiction: Optional[str] = None) -> JurisdictionRuleSet:
        target = jurisdiction or getattr(settings, "DEFAULT_JURISDICTION", "MAHARASHTRA")
        try:
            enum_key = StatutoryJurisdiction(target.upper())
            return JURISDICTION_REGISTRY.get(enum_key, JURISDICTION_REGISTRY[StatutoryJurisdiction.MAHARASHTRA])
        except (ValueError, KeyError):
            return JURISDICTION_REGISTRY[StatutoryJurisdiction.MAHARASHTRA]

statutory_rules = StatutoryRuleEngine()
