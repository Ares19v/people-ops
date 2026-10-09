"""
PeopleOps — Human-Readable ID Generators
=========================================
Generates clean, professional, readable identifier tags for enterprise entities
instead of long unreadable UUID strings (e.g., EMP-001, LV-2026-X8F2, TS-2026-K9M1).
"""

import time
import random
import string


def generate_readable_id(prefix: str, length: int = 4) -> str:
    """Generates a clean prefixed ID like LV-2026-A8K2 or TS-2026-B9F1."""
    chars = string.ascii_uppercase + string.digits
    # remove ambiguous chars like O, 0, I, 1
    clean_chars = [c for c in chars if c not in ("O", "0", "I", "1")]
    random_str = "".join(random.choices(clean_chars, k=length))
    year = time.strftime("%Y")
    
    if prefix in ("EMP", "USR", "PRJ", "PRF"):
        return f"{prefix}-{random_str}"
    return f"{prefix}-{year}-{random_str}"
