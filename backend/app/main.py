import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
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

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables if not exist and seed initial demo data
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await seed_initial_data()
    except Exception as e:
        print(f"Startup DB init notice: {e}")
    yield
    # Shutdown
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
