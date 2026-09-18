import pytest
import pytest_asyncio
import os
from app.core.database import engine, Base
from data.seed_data import seed_initial_data

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_initial_data()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if os.path.exists("./test_hr.db"):
        try:
            os.remove("./test_hr.db")
        except Exception:
            pass
