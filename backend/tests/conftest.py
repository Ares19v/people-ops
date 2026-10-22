import pytest
import pytest_asyncio
import os
from app.core.database import engine, Base
from data.seed_data import seed_initial_data

def pytest_collection_modifyitems(config, items):
    """Tests marked live_llm need a real provider; skip them unless explicitly enabled."""
    if os.environ.get("RUN_LIVE_LLM_TESTS") == "1":
        return
    skip = pytest.mark.skip(reason="needs a live LLM; set RUN_LIVE_LLM_TESTS=1 and MOCK_LLM_ENABLED=false")
    for item in items:
        if "live_llm" in item.keywords:
            item.add_marker(skip)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    try:
        async with engine.begin() as conn:
            # Start from a clean slate so tests are repeatable (state from earlier runs
            # used to make e.g. the leave-overlap test fail). Only ever on the throwaway test DB.
            if "test_hr.db" in str(engine.url):
                await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await seed_initial_data()
    except Exception as e:
        print(f"Test DB setup note: {e}")
    yield
    try:
        await engine.dispose()
    except Exception:
        pass
