from __future__ import annotations

import json
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

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_token = HTTPBearer(auto_error=False)

# Simple in-memory rate limiting: {api_key: [timestamps]}
# In production, use Redis.
RATE_LIMIT_STORE: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_REQUESTS = 60
RATE_LIMIT_WINDOW_SEC = 60.0
JWKS_CACHE_TTL_SEC = 300.0
_JWKS_CACHE: tuple[float, dict[str, dict[str, Any]]] | None = None


@dataclass(slots=True)
class ClerkAuthUser:
    user_id: str
    session_id: str | None
    issuer: str | None
    authorized_party: str | None
    claims: dict[str, Any]


def _rate_limit_key(connection: HTTPConnection, api_key: str | None) -> str:
    if api_key:
        return api_key
    host = connection.client.host if connection.client else "unknown"
    return f"public:{host}"


def get_api_key(
    connection: HTTPConnection, api_key_header: str | None = Security(api_key_header)
) -> str:
    """
    Dependency to validate API key and apply rate limits.
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

    # Rate Limiting
    now = time.time()
    rate_key = _rate_limit_key(connection, api_key_header)
    call_history = RATE_LIMIT_STORE[rate_key]

    # Clean up old timestamps outside the window
    call_history = [t for t in call_history if now - t < RATE_LIMIT_WINDOW_SEC]

    if len(call_history) >= RATE_LIMIT_REQUESTS:
        RATE_LIMIT_STORE[rate_key] = call_history
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
        )

    call_history.append(now)
    RATE_LIMIT_STORE[rate_key] = call_history

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
