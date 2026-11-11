import asyncio
import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.database import get_session, make_engine
from app.main import create_app
from app.seed import load_manifest, seed_schemes

BACKEND = Path(__file__).resolve().parents[1]
MANIFEST = Path(os.getenv("SEED_DATA_PATH", str(BACKEND.parent / "data/scholarships.json")))


@pytest.fixture(scope="session")
def test_settings():
    value = os.getenv("TEST_DATABASE_URL")
    if not value:
        pytest.fail("PostgreSQL integration tests require TEST_DATABASE_URL. Use python -m tests.run.")
    url = make_url(value)
    if url.drivername != "postgresql+asyncpg" or not (url.database or "").endswith("_test"):
        pytest.fail("Refusing to test against a non-PostgreSQL or non-test database.")
    return Settings(database_url=value, app_env="test", cors_origins=["http://localhost:3000"])


@pytest_asyncio.fixture(scope="session")
async def database(test_settings):
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "alembic",
        "upgrade",
        "head",
        cwd=BACKEND,
        env=os.environ | {"DATABASE_URL": test_settings.sqlalchemy_url.render_as_string(hide_password=False)},
    )
    assert await process.wait() == 0
    engine = make_engine(test_settings)
    async with async_sessionmaker(engine).begin() as session:
        assert await seed_schemes(session, load_manifest(MANIFEST)) == {"inserted": 5, "preserved": 0}
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(database):
    async with database.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as session:
            yield session
        await transaction.rollback()


@pytest_asyncio.fixture
async def client(test_settings, session):
    app = create_app(test_settings)

    async def override_session():
        yield session

    app.dependency_overrides[get_session] = override_session
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
        ) as client:
            yield client
