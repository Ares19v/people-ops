"""
PeopleOps — Centralised Logging & Telemetry Configuration
==========================================================
Provides:
  • configure_logging()   — Startup structlog & stdlib logging configuration
  • AgentLogger           — Rich structured event logger for ADK agents
  • log_tool_call()       — Async decorator for ADK DB tools
"""
from __future__ import annotations

import functools
import logging
import time
import traceback
from typing import Any, Callable

import structlog
from app.core.config import settings

# ── ANSI Terminal Colors ───────────────────────────────────────────────────────
_RESET   = "\033[0m"
_BOLD    = "\033[1m"
_CYAN    = "\033[96m"
_GREEN   = "\033[92m"
_YELLOW  = "\033[93m"
_MAGENTA = "\033[95m"
_RED     = "\033[91m"
_BLUE    = "\033[94m"
_DIM     = "\033[2m"

AGENT_COLORS: dict[str, str] = {
    "hr_root_orchestrator": _CYAN,
    "leave_agent":          _GREEN,
    "timesheet_agent":      _BLUE,
    "health_agent":         _MAGENTA,
    "policy_agent":         _YELLOW,
    "zoho_agent":           _CYAN,
    "statutory_critic":     _RED,
}


def configure_logging() -> None:
    """Configure structlog + stdlib logging once at startup."""
    log_level = logging.DEBUG if settings.ENVIRONMENT == "development" else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
    )

    for noisy in ("httpx", "httpcore", "asyncio", "urllib3", "sqlalchemy.engine", "google_genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=shared_processors + [structlog.dev.ConsoleRenderer(colors=True)],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


class AgentLogger:
    """Rich structured logger for Google ADK Agent lifecycle events."""

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        self.color = AGENT_COLORS.get(agent_name, _CYAN)
        self._slog = structlog.get_logger(f"agent.{agent_name}")

    def agent_start(self, session_id: str, user_id: str, message: str) -> None:
        preview = message[:80] + "…" if len(message) > 80 else message
        print(
            f"{self.color}{_BOLD}[AGENT ▶]{_RESET} "
            f"{_BOLD}{self.agent_name}{_RESET} | "
            f"sess={session_id[:12]} user={user_id[:8]} | "
            f'"{preview}"'
        )
        self._slog.info("agent_start", session_id=session_id, user_id=user_id)

    def agent_delegated(self, from_agent: str, to_agent: str) -> None:
        to_color = AGENT_COLORS.get(to_agent, _CYAN)
        print(
            f"{_YELLOW}{_BOLD}[ROUTING ↳]{_RESET} "
            f"{from_agent} ──delegated-to──▶ {to_color}{_BOLD}{to_agent}{_RESET}"
        )
        self._slog.info("agent_delegated", from_agent=from_agent, to_agent=to_agent)

    def agent_event(self, event_type: str, author: str, details: str = "") -> None:
        if details:
            print(f"{_DIM}[EVENT: {event_type} by {author}] {details[:100]}{_RESET}")

    def agent_done(self, final_agent: str, latency_ms: int, response: str, session_id: str) -> None:
        preview = response[:120].replace("\n", " ") + "…" if len(response) > 120 else response.replace("\n", " ")
        print(
            f"{_GREEN}{_BOLD}[RESPONSE ✔]{_RESET} "
            f"{final_agent} in {latency_ms}ms | "
            f'"{preview}"'
        )
        self._slog.info("agent_done", final_agent=final_agent, latency_ms=latency_ms, session_id=session_id)

    def agent_error(self, error: Exception, session_id: str) -> None:
        print(
            f"{_RED}{_BOLD}[AGENT ✘ ERROR]{_RESET} "
            f"{self.agent_name} | {type(error).__name__}: {error}"
        )
        self._slog.error("agent_error", error=str(error), exc_info=True, session_id=session_id)


def log_tool_call(func: Callable) -> Callable:
    """Decorator for async ADK DB tools to log execution time and outcome."""
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        tool_name = func.__name__

        # Sanitize argument representation
        safe_kwargs = {k: v for k, v in kwargs.items() if not any(s in k.lower() for s in ("token", "password", "secret"))}
        arg_str = ", ".join(f"{k}={v!r}" for k, v in list(safe_kwargs.items())[:3])
        if len(safe_kwargs) > 3:
            arg_str += ", …"

        try:
            result = await func(*args, **kwargs)
            duration_ms = int((time.monotonic() - start) * 1000)

            is_error = isinstance(result, dict) and "error" in result
            if is_error:
                err_msg = result.get("error", "Unknown error")
                print(
                    f"{_RED}[TOOL ✘]{_RESET} "
                    f"{_BOLD}{tool_name}{_RESET}({arg_str}) "
                    f"→ {_RED}{err_msg}{_RESET} ({duration_ms}ms)"
                )
            else:
                summary = "OK"
                if isinstance(result, dict):
                    summary = result.get("status") or result.get("message") or f"{len(result)} keys"
                print(
                    f"{_GREEN}[TOOL ✔]{_RESET} "
                    f"{_BOLD}{tool_name}{_RESET}({arg_str}) "
                    f"→ {summary} ({duration_ms}ms)"
                )

            return result

        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            print(
                f"{_RED}[TOOL ✘ CRASH]{_RESET} "
                f"{_BOLD}{tool_name}{_RESET} failed after {duration_ms}ms: {exc}"
            )
            # ADK tools should return error dicts, not raise
            return {"error": f"Tool execution failed: {str(exc)}"}

    return wrapper
