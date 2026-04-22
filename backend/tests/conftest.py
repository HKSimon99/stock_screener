import pytest
import psycopg2
from sqlalchemy import text
from sqlalchemy import create_engine
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.api.auth import get_clerk_user
from app.core.config import settings
from app.core.database import Base, get_db, get_read_db

# Tests run against the real app schema (consensus_app).
# Tables are created by Alembic migrations; this fixture only ensures
# they exist (create_all is a no-op when tables already exist) and
# truncates them between tests for isolation.
TEST_SCHEMA = settings.postgres_schema  # "consensus_app"
TEST_DB_HOST = "localhost"
TEST_DB_PORT = 5432
TEST_DB_NAME = "consensus_test"
TEST_DB_USER = "consensus"
TEST_DB_PASSWORD = "changeme"
TEST_ADMIN_DB = "postgres"
TEST_ADMIN_USER = "postgres"
TEST_ADMIN_PASSWORD = "changeme"


def _build_sync_test_url(database: str) -> str:
    return (
        f"postgresql+psycopg2://{TEST_DB_USER}:{TEST_DB_PASSWORD}"
        f"@{TEST_DB_HOST}:{TEST_DB_PORT}/{database}"
        f"?options=-csearch_path%3D{TEST_SCHEMA}"
    )


def _build_async_test_url(database: str) -> str:
    return (
        f"postgresql+asyncpg://{TEST_DB_USER}:{TEST_DB_PASSWORD}"
        f"@{TEST_DB_HOST}:{TEST_DB_PORT}/{database}"
    )


TEST_SYNC_DATABASE_URL = _build_sync_test_url(TEST_DB_NAME)
TEST_ASYNC_DATABASE_URL = _build_async_test_url(TEST_DB_NAME)
TEST_ASYNCPG_CONNECT_ARGS = {"server_settings": {"search_path": TEST_SCHEMA}}


def _ensure_test_database_exists() -> None:
    admin_conn = psycopg2.connect(
        host=TEST_DB_HOST,
        port=TEST_DB_PORT,
        dbname=TEST_ADMIN_DB,
        user=TEST_ADMIN_USER,
        password=TEST_ADMIN_PASSWORD,
    )
    admin_conn.autocommit = True
    try:
        with admin_conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB_NAME,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{TEST_DB_NAME}" OWNER "{TEST_DB_USER}"')
    finally:
        admin_conn.close()


def _truncate_all_tables_sql() -> str | None:
    # Use fullname (schema.table) since models now have explicit schema set.
    table_names = [
        f'"{table.schema}"."{table.name}"' if table.schema else f'"{table.name}"'
        for table in reversed(Base.metadata.sorted_tables)
    ]
    if not table_names:
        return None
    return f"TRUNCATE TABLE {', '.join(table_names)} RESTART IDENTITY CASCADE"


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Ensure the schema + tables exist. Tables are already created by Alembic;
    create_all is safe to call (it's a no-op for existing tables)."""
    _ensure_test_database_exists()
    engine = create_engine(TEST_SYNC_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{TEST_SCHEMA}"'))
        Base.metadata.create_all(bind=conn, checkfirst=True)
    engine.dispose()
    yield


@pytest.fixture
async def db_session():
    """Provide a database session for a test and truncate all tables in teardown.

    Teardown truncates *after* the session is closed, so there is no live
    connection holding locks when TRUNCATE tries to acquire AccessExclusiveLock.
    This avoids the deadlock that occurred when a separate autouse fixture fired
    TRUNCATE at the start of the next test while the previous test's session was
    still being released.
    """
    # Use settings.asyncpg_connect_args so SSL + explicit schema are applied.
    test_engine = create_async_engine(
        TEST_ASYNC_DATABASE_URL,
        echo=False,
        connect_args=TEST_ASYNCPG_CONNECT_ARGS,
    )
    TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        yield session
    # Session is fully closed here; now truncate safely.
    truncate_sql = _truncate_all_tables_sql()
    if truncate_sql:
        async with test_engine.begin() as conn:
            await conn.execute(text(truncate_sql))
    await test_engine.dispose()


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_read_db():
        yield db_session

    async def override_get_clerk_user():
        return {"user_id": "user_test_123"}

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_read_db] = override_get_read_db
    app.dependency_overrides[get_clerk_user] = override_get_clerk_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def unauth_client(db_session):
    async def override_get_db():
        yield db_session

    async def override_get_read_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_read_db] = override_get_read_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
