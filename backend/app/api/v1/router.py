from fastapi import APIRouter
from app.api.v1.endpoints import health

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])

# Registered later as each phase completes:
# from app.api.v1.endpoints import rankings, instruments, filters, snapshots, market_regime, alerts, strategies
# api_router.include_router(rankings.router,      prefix="/rankings",      tags=["rankings"])
# api_router.include_router(instruments.router,   prefix="/instruments",   tags=["instruments"])
# api_router.include_router(filters.router,       prefix="/filters",       tags=["filters"])
# api_router.include_router(snapshots.router,     prefix="/snapshots",     tags=["snapshots"])
# api_router.include_router(market_regime.router, prefix="/market-regime", tags=["market-regime"])
# api_router.include_router(alerts.router,        prefix="/alerts",        tags=["alerts"])
# api_router.include_router(strategies.router,    prefix="/strategies",    tags=["strategies"])
