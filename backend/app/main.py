import logging
import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import configure_logging

configure_logging()
from app.core.database import engine, Base
from app.api.v1.auth import router as auth_router
from app.api.v1.onboarding import router as onboarding_router
from app.api.v1.leaves import router as leaves_router
from app.api.v1.timesheets import router as timesheets_router
from app.api.v1.reports import router as reports_router
from app.api.v1.policy import router as policy_router
from app.api.v1.agents import router as agents_router
from app.api.v1.health import router as health_router
from data.seed_data import seed_initial_data

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables if not exist and seed initial demo data
    watcher_task = None
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await seed_initial_data()
        from app.core.db_views import initialize_database_views
        await initialize_database_views()
        from app.services.langfuse_prompt_service import langfuse_prompt_service
        from app.agents.adk_fleet import sync_agent_instructions
        # Agent prompts are strictly managed via Langfuse Cloud (not PostgreSQL)
        await langfuse_prompt_service.load_prompts_from_langfuse()
        sync_agent_instructions()
        # Launch real-time background watcher for Langfuse Cloud prompt edits & PostgreSQL auto-revert
        watcher_task = asyncio.create_task(langfuse_prompt_service.start_background_watcher())
    except Exception as e:
        logger.warning(f"Startup DB init notice: {e}")
    yield
    # Shutdown
    if watcher_task:
        try:
            from app.services.langfuse_prompt_service import langfuse_prompt_service
            langfuse_prompt_service.stop_background_watcher()
            watcher_task.cancel()
        except Exception:
            logger.debug("Suppressed non-fatal error", exc_info=True)
    # Make sure buffered traces/scores reach Langfuse before the process exits.
    try:
        from app.observability import langfuse_client
        langfuse_client.shutdown()
    except Exception as exc:
        logger.warning("Langfuse shutdown failed: %s", exc)
    await engine.dispose()

app = FastAPI(
    title=settings.APP_NAME,
    description="Production-oriented HR platform with Google ADK Multi-Agent architecture and NVIDIA NeMo Guardrails.",
    version="1.0.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(health_router, prefix=settings.API_V1_STR)
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(onboarding_router, prefix=settings.API_V1_STR)
app.include_router(leaves_router, prefix=settings.API_V1_STR)
app.include_router(timesheets_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(policy_router, prefix=settings.API_V1_STR)
app.include_router(agents_router, prefix=settings.API_V1_STR)

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": f"{settings.API_V1_STR}/docs",
        "status": "online"
    }
