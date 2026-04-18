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

engine = create_async_engine(settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    engine,
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
