"""Keep evaluation / benchmark runs out of real employee data.

Experiments drive the real orchestrator, which persists every turn. Run under a real employee's
identity and an ordinary session id, they got folded into that employee's actual chat history
(session ids are normalised to `sess_<employee>_<n>`) and collided with real turn ids.

Rules used by every evaluation harness:
  * session ids start with `test_` (the session-id normaliser leaves those untouched),
  * traces carry an evaluation-only email instead of the employee's,
  * each evaluation session is deleted as soon as it has been scored.
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

EVAL_USER_EMAIL = "eval.benchmarks@intelera.com"


def eval_session_id(tag: str) -> str:
    return f"test_eval_{tag}_{int(time.time() * 1000)}"


async def discard_eval_session(session_id: str) -> None:
    """Delete an evaluation session (memory, disk cache and database rows). Never raises."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.memory.conversation_memory import conversation_memory

        async with AsyncSessionLocal() as db:
            await conversation_memory.clear_session_async(session_id, db=db)
    except Exception as exc:
        logger.warning("Could not discard evaluation session %s: %s", session_id, exc)
