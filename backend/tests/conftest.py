import pytest
from sqlalchemy import text
from sqlalchemy import create_engine
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.api.auth import get_clerk_user
from app.core.config import settings
from app.core.database import Base, get_db

TEST_SCHEMA = "consensus_test"


def _truncate_all_tables_sql() -> str | None:
    table_names = [f'"{table.name}"' for table in reversed(Base.metadata.sorted_tables)]
    if not table_names:
        return None
    return f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE"


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    engine = create_engine(settings.sync_database_url)
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{TEST_SCHEMA}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TEST_SCHEMA}"'))
        conn.execute(text(f'SET search_path TO "{TEST_SCHEMA}", public'))
        translated = conn.execution_options(schema_translate_map={None: TEST_SCHEMA})
        Base.metadata.create_all(translated)
    yield
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{TEST_SCHEMA}" CASCADE'))
    engine.dispose()


@pytest.fixture
async def db_session():
    test_engine = create_async_engine(
        settings.database_url,
        echo=False,
        connect_args={"server_settings": {"search_path": TEST_SCHEMA}},
    )
    TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        truncate_sql = _truncate_all_tables_sql()
        if truncate_sql:
            await session.execute(text(truncate_sql))
            await session.commit()
        yield session
        if truncate_sql:
            await session.execute(text(truncate_sql))
            await session.commit()
    await test_engine.dispose()


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_clerk_user():
        return {"user_id": "user_test_123"}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_clerk_user] = override_get_clerk_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def unauth_client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
