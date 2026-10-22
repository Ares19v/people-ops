"""Single source of truth for employee identity lookups.

Maps employee IDs, role aliases and legacy identifiers to a name and corporate email.
The values mirror `data/seed_data.py`; everything that needs to turn "EMP-004" into a
name or an email (tracing, memory headers, session ids) must go through here instead
of keeping its own copy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class Person:
    employee_id: str
    full_name: str
    email: str
    aliases: Tuple[str, ...] = ()

    @property
    def email_prefix(self) -> str:
        return self.email.split("@")[0]


_PEOPLE = (
    Person("EMP-001", "Devansh Tyagi", "devansh.tyagi@intelera.com", ("ADMIN", "DEVANSH")),
    Person("EMP-002", "Vikram Malhotra", "vikram.malhotra@intelera.com", ("MANAGER", "HR")),
    Person("EMP-003", "Priya Patel", "priya.patel@intelera.com", ("ASSOCIATE",)),
    Person("EMP-004", "Aarav Sharma", "aarav.sharma@intelera.com", ("EMPLOYEE", "EMP-7701")),
    Person("EMP-005", "Sneha Kulkarni", "sneha.kulkarni@intelera.com", ("EMPLOYEE2",)),
)

# Synthetic identities used by benchmarks / QA automation (no human name).
_SERVICE_EMAILS: Dict[str, str] = {
    "USR-EVAL-999": "eval.benchmarks@intelera.com",
    "EVAL-USER": "eval.benchmarks@intelera.com",
    "USR-TEST-101": "qa.automation@intelera.com",
}

_INDEX: Dict[str, Person] = {}
for _p in _PEOPLE:
    for _key in (_p.employee_id, *_p.aliases):
        _INDEX[_key] = _p


def _normalise(identifier: str) -> str:
    key = identifier.strip().upper().replace("_", "-").replace(" ", "-")
    return key[4:] if key.startswith("USR-") and key[4:] in _INDEX else key


def lookup(identifier: Optional[str]) -> Optional[Person]:
    """Find a person by employee id, alias, or email. Returns None if unknown."""
    if not identifier:
        return None
    raw = str(identifier).strip()
    if "@" in raw:
        low = raw.lower()
        return next((p for p in _PEOPLE if p.email == low), None)
    return _INDEX.get(_normalise(raw))


def name_for(identifier: Optional[str]) -> Optional[str]:
    person = lookup(identifier)
    return person.full_name if person else None


def email_for(identifier: Optional[str]) -> Optional[str]:
    """Corporate email for a known identifier (people or service accounts), else None."""
    person = lookup(identifier)
    if person:
        return person.email
    if identifier:
        return _SERVICE_EMAILS.get(str(identifier).strip().upper().replace("_", "-"))
    return None


def email_prefix_for(identifier: Optional[str]) -> Optional[str]:
    email = email_for(identifier)
    return re.sub(r"[^a-z0-9.]", "", email.split("@")[0].lower()) if email else None
