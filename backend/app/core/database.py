from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.core.config import settings

# When Neon's built-in PgBouncer pooler is active (POSTGRES_HOST_POOLER is set),
# use NullPool so SQLAlchemy doesn't maintain its own pool on top of PgBouncer's.
# For local dev / non-pooled Postgres, use the default connection pool.
_use_null_pool = bool(settings.postgres_host_pooler)
_engine_kwargs: dict = {
    "echo": settings.app_env == "development",
    "connect_args": settings.asyncpg_connect_args,
    "pool_pre_ping": True,  # Required: reconnect after Neon scale-to-zero idle timeout
}
if _use_null_pool:
    _engine_kwargs["poolclass"] = NullPool
else:
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

# ── Primary (read-write) engine ──────────────────────────────────────────────
engine = create_async_engine(settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Read replica engine ───────────────────────────────────────────────────────
# When POSTGRES_HOST_REPLICA is set (Neon read replica compute endpoint),
# read-only endpoints (rankings, instruments, market regime) route here to
# reduce load on the primary write connection.
# Falls back to the primary engine when the replica is not configured so that
# local dev and CI environments work without any extra setup.
_replica_url = settings.database_url_replica
if _replica_url:
    _replica_kwargs: dict = {
        "echo": False,  # Keep replica queries quiet in logs
        "connect_args": settings.asyncpg_connect_args,
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
    }
    read_engine = create_async_engine(_replica_url, **_replica_kwargs)
else:
    read_engine = engine  # fallback: replica == primary

AsyncReadSessionLocal = async_sessionmaker(
    read_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_read_db() -> AsyncSession:
    """
    Yields a read-only session routed to the Neon read replica when configured,
    otherwise falls back to the primary.  Use this for GET endpoints that do not
    write to the database (rankings, instruments, market regime, etc.).
    """
    async with AsyncReadSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
