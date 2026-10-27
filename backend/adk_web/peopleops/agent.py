"""ADK Web entry point: the PeopleOps HR agent fleet.

`root_agent` is the SAME `hr_root_orchestrator` object the backend runs (root -> leave / timesheet /
health / policy / zoho sub-agents, same tools, same Langfuse-managed prompts). Start it with
`python scripts/run_adk_web.py` (or `npm run adk:web`) and open the Eval tab.

Safety: ADK Web lets anyone chat with agents whose tools write to the database (apply leave, log
hours). This module therefore points the app at a local SQLite file and refuses to start against
anything else, unless ADK_WEB_ALLOW_REAL_DB=1 is set explicitly. ADK loads the project .env with
`override=True` *before* importing this file, so the override has to happen here, not in a launcher.
"""
import asyncio
import os
import sys
import threading
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

_ALLOW_REAL_DB = os.environ.get("ADK_WEB_ALLOW_REAL_DB") == "1"

# Free-tier providers (Groq: 8k tokens/min) rate-limit a multi-call agent turn; wait and retry instead of failing.
os.environ.setdefault("LLM_NUM_RETRIES", "5")

if not _ALLOW_REAL_DB:
    _db_file = Path(os.environ.get("ADK_WEB_DB_FILE") or (_BACKEND_DIR / "data" / "adk_web.db")).resolve()
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_db_file.as_posix()}"
    os.environ["SYNC_DATABASE_URL"] = f"sqlite:///{_db_file.as_posix()}"
    # A distinct Langfuse environment keeps ADK Web traces apart from the API's and the grid's.
    os.environ["ENVIRONMENT"] = os.environ.get("ADK_WEB_ENVIRONMENT", "adk-web")

from app.core.config import settings  # noqa: E402  (must come after the environment is prepared)

if not _ALLOW_REAL_DB and "sqlite" not in settings.DATABASE_URL:
    raise RuntimeError(
        "Refusing to start ADK Web against a non-SQLite database. "
        "Import the app only after this module has prepared the environment, or set ADK_WEB_ALLOW_REAL_DB=1."
    )


def _initialise_database() -> None:
    """Create the tables and demo employees in the local database (idempotent)."""
    from app.core.database import Base, engine
    from data.seed_data import seed_initial_data

    async def _run() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await seed_initial_data()

    # ADK imports agents inside its own running event loop, so use a separate thread with its own loop.
    worker = threading.Thread(target=lambda: asyncio.run(_run()), name="adk-web-db-init")
    worker.start()
    worker.join()


_initialise_database()

from app.agents.adk_fleet import hr_root_orchestrator  # noqa: E402
from app.evaluations.adk_support import install_identity_shim  # noqa: E402

install_identity_shim(hr_root_orchestrator, refresh_prompts=True)

# Optional: pick the model for this ADK Web process (e.g. ADK_WEB_MODEL=openai/gpt-4o-mini).
_model = os.environ.get("ADK_WEB_MODEL")
if _model:
    from app.agents.adk_fleet import refresh_adk_fleet_models  # noqa: E402
    from app.core.llm_bridge import set_active_model  # noqa: E402

    refresh_adk_fleet_models(set_active_model(_model))

root_agent = hr_root_orchestrator
