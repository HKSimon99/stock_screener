import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentry — initialised only when SENTRY_DSN is set in the environment.
# This is a no-op in local development and test environments.
# ---------------------------------------------------------------------------
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        # Send 100 % of error events regardless of traces_sample_rate.
        profiles_sample_rate=0.0,
        # Don't leak PII
        send_default_pii=False,
    )

@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: ARG001
    """
    FastAPI lifespan handler — replaces the deprecated @app.on_event("startup").
    Runs health checks on startup, then yields control for the app's lifetime.
    """
    from sqlalchemy import text  # noqa: PLC0415
    from app.core.database import AsyncSessionLocal  # noqa: PLC0415

    checks: dict[str, str] = {}

    # 1. Database connectivity
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["db_connection"] = "OK"
    except Exception as exc:
        checks["db_connection"] = f"FAIL: {exc}"
        logger.critical("[startup] DB connection failed — cannot continue: %s", exc)
        raise RuntimeError("Database unreachable on startup") from exc

    # 2. Consensus scores populated (warn if table is empty)
    try:
        async with AsyncSessionLocal() as session:
            row = await session.execute(
                text("SELECT COUNT(*) FROM consensus_app.consensus_scores")
            )
            count = row.scalar_one()
        checks["consensus_scores"] = (
            "WARN: table is empty — run the scoring pipeline" if count == 0
            else f"OK ({count} rows)"
        )
    except Exception as exc:
        checks["consensus_scores"] = f"WARN: could not query ({exc})"

    # 3. Alembic migration state visible. This catches accidental schema resets
    # before the app starts serving with a partially restored database.
    try:
        schema = (settings.postgres_schema or "public").replace('"', '""')
        async with AsyncSessionLocal() as session:
            row = await session.execute(
                text(f'SELECT version_num FROM "{schema}".alembic_version LIMIT 1')
            )
            version = row.scalar_one_or_none()
        checks["alembic_version"] = (
            f"OK ({version})" if version else "WARN: no alembic version recorded"
        )
    except Exception as exc:
        checks["alembic_version"] = f"WARN: could not query ({exc})"

    # 4. CORS origins include a non-localhost origin in production
    non_local = [
        o for o in settings.cors_origins_list
        if "localhost" not in o and "127.0.0.1" not in o
    ]
    if settings.app_env == "production" and not non_local:
        checks["cors_origins"] = (
            "WARN: no production domain in CORS_ORIGINS — frontend will be blocked"
        )
    else:
        checks["cors_origins"] = f"OK ({len(settings.cors_origins_list)} origin(s) configured)"

    # 5. SECRET_KEY is not the insecure default
    checks["secret_key"] = (
        "WARN: SECRET_KEY is still 'changeme' — change before production use"
        if settings.secret_key == "changeme"
        else "OK"
    )

    # Emit one structured log line per check
    for check, status in checks.items():
        level = logging.WARNING if status.startswith(("WARN", "FAIL")) else logging.INFO
        logger.log(level, "[startup] %-22s %s", check, status)

    yield  # app runs here


app = FastAPI(
    title="Consensus Stock Research Platform",
    description="Multi-strategy consensus stock screener — US & Korea",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)

# ---------------------------------------------------------------------------
# OpenTelemetry — env-gated, no-op when OTLP_ENDPOINT is absent.
# Must be called AFTER app and router are fully configured so the FastAPI
# instrumentor can see all registered routes.
# ---------------------------------------------------------------------------
from app.core.telemetry import setup_telemetry  # noqa: E402
from app.core.database import engine as _db_engine  # noqa: E402

setup_telemetry(app, engine=_db_engine)
