import pytest
import pytest_asyncio
import os
from app.core.database import engine, Base
from data.seed_data import seed_initial_data

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await seed_initial_data()
    except Exception as e:
        print(f"Test DB setup note: {e}")
    yield
    try:
        await engine.dispose()
    except Exception:
        pass
