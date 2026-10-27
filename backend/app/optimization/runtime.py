"""Isolated ADK runtime shared by the ADK grid and the optimisers.

ADK evaluations run the real agents, whose tools write to the database (apply leave, log hours). Importing the
`peopleops` ADK Web package prepares a local SQLite file and refuses to start against anything else, so scripts
go through it. This module must be called BEFORE anything else under `app.` is imported.
"""
from __future__ import annotations

import importlib
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

BACKEND_DIR = Path(__file__).resolve().parents[2]
ADK_WEB_DIR = BACKEND_DIR / "adk_web"


_BRACES = re.compile(r"\{+([^{}]*)\}+")


def to_adk_instruction(text: str) -> str:
    """Make prompt text safe to use as an ADK instruction.

    ADK reads `{name}` in an instruction as a session variable and raises if it is missing. Langfuse prompts use
    `{{organization_name}}`; that one is rendered the way production does it, and any other brace group (a JSON
    example, a placeholder an optimiser invented) becomes `[...]` so it is read as plain text.
    """
    from app.services.langfuse_prompt_service import langfuse_prompt_service

    return _BRACES.sub(lambda m: f"[{m.group(1).strip()}]", langfuse_prompt_service._render(text))


def prepare_adk_runtime(model: Optional[str] = None) -> Any:
    """Return the isolated `hr_root_orchestrator`; the caller then sets prompt and model per cell.

    The ADK Web package installs a callback that re-reads the *live* prompts on every model call. Grid and
    optimisation runs choose the root prompt themselves, so that callback is replaced by the plain
    identity shim (employee header + current time, no Langfuse fetch per turn).
    """
    for path in (str(BACKEND_DIR), str(ADK_WEB_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)
    if model:
        os.environ["ADK_WEB_MODEL"] = model
    os.environ.setdefault("LLM_NUM_RETRIES", "5")
    agent_module = importlib.import_module("peopleops.agent")

    from app.evaluations.adk_support import install_identity_shim

    install_identity_shim(agent_module.root_agent, refresh_prompts=False)
    return agent_module.root_agent
