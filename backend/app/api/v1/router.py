from fastapi import APIRouter
from app.api.v1.endpoints import health

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])

from app.api.v1.endpoints import rankings, instruments, strategies, meta, risk, search, users

api_router.include_router(users.router,         prefix="/users",         tags=["users"])
api_router.include_router(rankings.router,      prefix="/rankings",      tags=["rankings"])
api_router.include_router(instruments.router,   prefix="/instruments",   tags=["instruments"])
api_router.include_router(strategies.router,    prefix="/strategies",    tags=["strategies"])
api_router.include_router(strategies.filter_router, prefix="/filters",   tags=["filters"])
api_router.include_router(meta.router,          tags=["meta"]) # /market-regime, /snapshots, /alerts, /scoring
api_router.include_router(risk.router,          prefix="/risk",          tags=["risk"])
api_router.include_router(search.router,        tags=["search"])
