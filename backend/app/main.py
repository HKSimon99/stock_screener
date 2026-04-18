import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router

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

app = FastAPI(
    title="Consensus Stock Research Platform",
    description="Multi-strategy consensus stock screener — US & Korea",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
