"""
PeopleOps — Clean Semantic Sequential ID Generator
==================================================
Generates clean, professional, readable sequential identifiers across all platform entities:
- Sessions: sess_devansh.tyagi_1, sess_priya.patel_1
- Turns: turn_devansh.tyagi_1_1, turn_priya.patel_1_2
- Summaries: sum_devansh.tyagi_1
- Leaves: leave_aarav.sharma_1, leave_priya.patel_1
- Balances: bal_aarav.sharma_el, bal_priya.patel_cl
- Timesheets: ts_aarav.sharma_1, ts_devansh.tyagi_1
- Documents: doc_aarav.sharma_aadhaar_1, doc_sneha.kulkarni_pan_1
- Audit Logs: aud_devansh.tyagi_1, aud_system_1
- Zoho Sync: sync_zoho_1, sync_zoho_2
- Projects: prj_banking_1, prj_ai_platform_2
"""

import re
import threading
from typing import Optional, Dict

_counters: Dict[str, int] = {}
_lock = threading.Lock()


def get_email_prefix(user_identifier: Optional[str]) -> str:
    """Extracts a clean first.last prefix from an email or user identifier."""
    if not user_identifier:
        return "devansh.tyagi"
    
    raw = str(user_identifier).strip().lower()
    if "@" in raw:
        prefix = raw.split("@")[0]
    else:
        # Map known EMP codes
        emp_map = {
            "emp-001": "devansh.tyagi",
            "emp-002": "vikram.malhotra",
            "emp-003": "priya.patel",
            "emp-004": "aarav.sharma",
            "emp-005": "sneha.kulkarni",
        }
        prefix = emp_map.get(raw, raw.replace("-", ".").replace("_", "."))
        
    clean = re.sub(r'[^a-z0-9.]', '', prefix).strip(".")
    return clean or "devansh.tyagi"


def get_next_sequence(category: str, key: str = "global") -> int:
    """Returns the next sequential integer (1-based) for a given category and entity key."""
    bucket = f"{category}:{key}".lower()
    with _lock:
        current = _counters.get(bucket, 0) + 1
        _counters[bucket] = current
        return current


def generate_entity_id(
    entity_type: str,
    user_identifier: Optional[str] = None,
    sub_type: Optional[str] = None,
    custom_index: Optional[int] = None
) -> str:
    """Generates clean sequential IDs with zero random numbers or hashes."""
    prefix = get_email_prefix(user_identifier)
    
    if entity_type == "session":
        idx = custom_index or get_next_sequence("session", prefix)
        return f"sess_{prefix}_{idx}"
        
    if entity_type == "turn":
        sess_key = user_identifier or "system"
        idx = custom_index or get_next_sequence("turn", sess_key)
        return f"turn_{prefix}_{idx}"
        
    if entity_type == "summary":
        idx = custom_index or get_next_sequence("summary", prefix)
        return f"sum_{prefix}_{idx}"
        
    if entity_type == "leave":
        idx = custom_index or get_next_sequence("leave", prefix)
        return f"leave_{prefix}_{idx}"
        
    if entity_type == "balance":
        st = (sub_type or "general").lower()
        return f"bal_{prefix}_{st}"
        
    if entity_type == "timesheet":
        idx = custom_index or get_next_sequence("timesheet", prefix)
        return f"ts_{prefix}_{idx}"
        
    if entity_type == "document":
        st = (sub_type or "doc").lower()
        idx = custom_index or get_next_sequence("document", f"{prefix}:{st}")
        return f"doc_{prefix}_{st}_{idx}"
        
    if entity_type == "audit":
        idx = custom_index or get_next_sequence("audit", prefix)
        return f"aud_{prefix}_{idx}"
        
    if entity_type == "sync":
        idx = custom_index or get_next_sequence("sync", "zoho")
        return f"sync_zoho_{idx}"
        
    if entity_type == "profile":
        return f"prf_{prefix}"
        
    idx = custom_index or get_next_sequence(entity_type, prefix)
    return f"{entity_type}_{prefix}_{idx}"


# Legacy alias
generate_readable_id = generate_entity_id
