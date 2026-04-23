from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, Security, status
from fastapi.requests import HTTPConnection
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_token = HTTPBearer(auto_error=False)

RATE_LIMIT_REQUESTS = 60
RATE_LIMIT_WINDOW_SEC = 60
HYDRATION_RATE_LIMIT_REQUESTS = 5
HYDRATION_RATE_LIMIT_WINDOW_SEC = 900
JWKS_CACHE_TTL_SEC = 300.0
_JWKS_CACHE: tuple[float, dict[str, dict[str, Any]]] | None = None

# ---------------------------------------------------------------------------
# Redis client — lazy singleton, None when REDIS_URL is not configured.
# Used for distributed rate limiting (INCR + EXPIRE fixed-window approach).
# Falls back to the in-memory store for local development.
# ---------------------------------------------------------------------------
_redis_client: Any | None = None  # redis.asyncio.Redis


def _get_redis() -> Any | None:
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    if not settings.redis_url:
        return None
    try:
        import redis.asyncio as aioredis  # type: ignore[import-untyped]

        _redis_client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    except Exception:  # pragma: no cover
        logger.warning("Redis rate limiter unavailable — falling back to in-memory store")
        _redis_client = None
    return _redis_client


# In-memory fallback: {rate_key: [timestamps]}
_RATE_LIMIT_STORE: dict[str, list[float]] = defaultdict(list)


@dataclass(slots=True)
class ClerkAuthUser:
    user_id: str
    session_id: str | None
    issuer: str | None
    authorized_party: str | None
    claims: dict[str, Any]


@dataclass(slots=True)
class AuthenticatedActor:
    actor_type: str
    actor_id: str
    requester_source: str
    user: ClerkAuthUser | None = None
    api_key: str | None = None


def _rate_limit_key(connection: HTTPConnection, api_key: str | None) -> str:
    if api_key:
        return f"apikey:{api_key}"
    host = connection.client.host if connection.client else "unknown"
    return f"public:{host}"


def _rate_limit_in_memory(
    rate_key: str,
    *,
    limit: int = RATE_LIMIT_REQUESTS,
    window_sec: int = RATE_LIMIT_WINDOW_SEC,
) -> None:
    """Sliding-window rate limit using the in-memory fallback store."""
    now = time.time()
    history = _RATE_LIMIT_STORE[rate_key]
    history = [t for t in history if now - t < window_sec]
    if len(history) >= limit:
        _RATE_LIMIT_STORE[rate_key] = history
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )
    history.append(now)
    _RATE_LIMIT_STORE[rate_key] = history


async def _rate_limit_redis(
    rate_key: str,
    *,
    limit: int = RATE_LIMIT_REQUESTS,
    window_sec: int = RATE_LIMIT_WINDOW_SEC,
) -> None:
    """
    Fixed-window rate limit via Redis INCR + EXPIRE.

    Pattern:
    1. INCR rate:{key}  → returns new count for this window
    2. If count == 1 (first hit), set EXPIRE so the key expires after the window
    3. If count > limit, raise 429

    Using a pipeline ensures the INCR and conditional EXPIRE are sent in one
    round-trip, but they are not atomic.  This is intentional — the worst case
    is a very small over-count on the first hit under extreme concurrency, which
    is acceptable for our 60-req/min limit.
    """
    client = _get_redis()
    if client is None:
        _rate_limit_in_memory(rate_key, limit=limit, window_sec=window_sec)
        return

    redis_key = f"rate:{rate_key}"
    try:
        pipe = client.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_sec, nx=True)
        results = await pipe.execute()
        count: int = results[0]
    except Exception as exc:  # pragma: no cover
        logger.warning("Redis rate limiter error (%s) — falling back to in-memory", exc)
        _rate_limit_in_memory(rate_key, limit=limit, window_sec=window_sec)
        return

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )


async def apply_rate_limit(
    rate_key: str,
    *,
    limit: int = RATE_LIMIT_REQUESTS,
    window_sec: int = RATE_LIMIT_WINDOW_SEC,
) -> None:
    await _rate_limit_redis(rate_key, limit=limit, window_sec=window_sec)


async def get_api_key(
    connection: HTTPConnection, api_key_header: str | None = Security(api_key_header)
) -> str:
    """
    Dependency to validate API key and apply rate limits.

    Uses Redis for distributed rate limiting when REDIS_URL is configured;
    falls back to an in-memory sliding-window store for local development.
    """
    if settings.app_env == "development" and not settings.api_keys:
        return "dev_unauthenticated"

    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    valid_keys = [k.strip() for k in settings.api_keys.split(",") if k.strip()]
    if api_key_header not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )

    rate_key = _rate_limit_key(connection, api_key_header)
    await _rate_limit_redis(rate_key, limit=RATE_LIMIT_REQUESTS, window_sec=RATE_LIMIT_WINDOW_SEC)

    return api_key_header


async def _fetch_clerk_jwks(force_refresh: bool = False) -> dict[str, dict[str, Any]]:
    global _JWKS_CACHE

    now = time.time()
    if not force_refresh and _JWKS_CACHE and now - _JWKS_CACHE[0] < JWKS_CACHE_TTL_SEC:
        return _JWKS_CACHE[1]

    headers: dict[str, str] = {}
    if settings.clerk_secret_key:
        headers["Authorization"] = f"Bearer {settings.clerk_secret_key}"

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(settings.clerk_jwks_url, headers=headers)
        response.raise_for_status()
        payload = response.json()

    keys = {
        key["kid"]: key
        for key in payload.get("keys", [])
        if isinstance(key, dict) and isinstance(key.get("kid"), str)
    }
    if not keys:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Clerk JWKS is unavailable",
        )

    _JWKS_CACHE = (now, keys)
    return keys


def _build_decode_kwargs() -> dict[str, Any]:
    audiences = settings.clerk_jwt_audiences_list
    kwargs: dict[str, Any] = {
        "algorithms": ["RS256"],
        "options": {
            "require": ["exp", "iat", "nbf", "sub"],
            "verify_aud": bool(audiences),
            "verify_iss": bool(settings.clerk_jwt_issuer),
        },
    }
    if audiences:
        kwargs["audience"] = audiences if len(audiences) > 1 else audiences[0]
    if settings.clerk_jwt_issuer:
        kwargs["issuer"] = settings.clerk_jwt_issuer
    return kwargs


def _validate_authorized_party(connection: HTTPConnection, claims: dict[str, Any]) -> None:
    authorized_party = claims.get("azp")
    if not isinstance(authorized_party, str) or not authorized_party:
        return

    origin = connection.headers.get("origin")
    if origin:
        if authorized_party != origin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Clerk authorized party",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return

    allowed_origins = set(settings.cors_origins_list)
    if allowed_origins and authorized_party not in allowed_origins:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clerk token origin is not allowed",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_clerk_user(
    connection: HTTPConnection,
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_token),
) -> ClerkAuthUser:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not settings.clerk_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Clerk authentication is not configured",
        )

    token = credentials.credentials

    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Clerk token header",
                headers={"WWW-Authenticate": "Bearer"},
            )

        jwks = await _fetch_clerk_jwks()
        jwk = jwks.get(kid)
        if jwk is None:
            jwks = await _fetch_clerk_jwks(force_refresh=True)
            jwk = jwks.get(kid)
        if jwk is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unknown Clerk signing key",
                headers={"WWW-Authenticate": "Bearer"},
            )

        signing_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
        claims = jwt.decode(token, signing_key, **_build_decode_kwargs())
        _validate_authorized_party(connection, claims)
    except HTTPException:
        raise
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clerk token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Clerk token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify Clerk token",
        ) from exc

    user_id = claims.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clerk token is missing a subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session_id = claims.get("sid")
    return ClerkAuthUser(
        user_id=user_id,
        session_id=session_id if isinstance(session_id, str) else None,
        issuer=claims.get("iss") if isinstance(claims.get("iss"), str) else None,
        authorized_party=claims.get("azp") if isinstance(claims.get("azp"), str) else None,
        claims=claims,
    )


async def get_optional_clerk_user(
    connection: HTTPConnection,
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_token),
) -> ClerkAuthUser | None:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        return None
    return await get_clerk_user(connection, credentials)


async def get_optional_api_key(
    connection: HTTPConnection,
    api_key_header_value: str | None = Security(api_key_header),
) -> str | None:
    if not api_key_header_value:
        return None
    return await get_api_key(connection, api_key_header_value)


async def get_authenticated_actor(
    auth_user: ClerkAuthUser | None = Security(get_optional_clerk_user),
    api_key: str | None = Security(get_optional_api_key),
) -> AuthenticatedActor:
    if auth_user is not None:
        return AuthenticatedActor(
            actor_type="user",
            actor_id=auth_user.user_id,
            requester_source="user",
            user=auth_user,
        )
    if api_key is not None:
        return AuthenticatedActor(
            actor_type="api_key",
            actor_id=api_key,
            requester_source="api_key",
            api_key=api_key,
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing bearer token or X-API-Key header",
        headers={"WWW-Authenticate": "Bearer"},
    )
