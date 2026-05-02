from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, Field

from app.api.deps import get_db, get_clerk_user
from app.api.auth import ClerkAuthUser
from app.models.user import User, UserPushToken

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Terms of Service / consent
# ─────────────────────────────────────────────────────────────────────────────

# Bumping this string forces all users to re-accept the ToS. The version is
# stored alongside tos_accepted_at so we can tell who accepted which revision.
CURRENT_TOS_VERSION = "2026-05-01"


class UserMeResponse(BaseModel):
    clerk_user_id:    str
    email:            Optional[str]    = None
    tos_accepted:     bool             # True iff tos_accepted_at AND tos_version == CURRENT_TOS_VERSION
    tos_accepted_at:  Optional[datetime] = None
    tos_version:      Optional[str]    = None
    current_tos_version: str


class AcceptTosRequest(BaseModel):
    """Body for POST /me/accept-tos.

    `version` is required so the client proves it accepted the version it
    actually rendered (prevents stale tabs from auto-accepting a new ToS).
    `email` is optional but recommended — captured at acceptance time so
    we can email about future ToS changes without round-tripping Clerk.
    """
    version: str
    email:   Optional[str] = Field(default=None, max_length=320)  # RFC 5321 max


async def _get_or_create_user(db: AsyncSession, clerk_user_id: str) -> User:
    result = await db.execute(select(User).where(User.clerk_user_id == clerk_user_id))
    user = result.scalars().first()
    if user is None:
        user = User(clerk_user_id=clerk_user_id)
        db.add(user)
        await db.flush()
    return user


def _is_current(user: User) -> bool:
    return user.tos_accepted_at is not None and user.tos_version == CURRENT_TOS_VERSION


@router.get("/me", response_model=UserMeResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    auth_user: ClerkAuthUser = Depends(get_clerk_user),
) -> UserMeResponse:
    """
    Returns the calling user's app-side state. Auto-creates the user row on
    first call so the frontend has something to bind to before they accept ToS.
    """
    user = await _get_or_create_user(db, auth_user.user_id)
    await db.commit()
    return UserMeResponse(
        clerk_user_id=user.clerk_user_id,
        email=user.email,
        tos_accepted=_is_current(user),
        tos_accepted_at=user.tos_accepted_at,
        tos_version=user.tos_version,
        current_tos_version=CURRENT_TOS_VERSION,
    )


@router.post("/me/accept-tos", response_model=UserMeResponse)
async def accept_tos(
    payload: AcceptTosRequest,
    db: AsyncSession = Depends(get_db),
    auth_user: ClerkAuthUser = Depends(get_clerk_user),
) -> UserMeResponse:
    """
    Records that the user accepted the ToS. The client must echo back the
    version string it rendered — if the server has bumped CURRENT_TOS_VERSION
    in between page-load and click, we reject so the user re-reads the new text.
    """
    if payload.version != CURRENT_TOS_VERSION:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"ToS version mismatch — current is '{CURRENT_TOS_VERSION}', client sent '{payload.version}'. Reload and re-accept.",
        )

    user = await _get_or_create_user(db, auth_user.user_id)
    user.tos_accepted_at = datetime.now(timezone.utc)
    user.tos_version = CURRENT_TOS_VERSION
    if payload.email:
        user.email = str(payload.email)
    await db.commit()
    await db.refresh(user)

    return UserMeResponse(
        clerk_user_id=user.clerk_user_id,
        email=user.email,
        tos_accepted=_is_current(user),
        tos_accepted_at=user.tos_accepted_at,
        tos_version=user.tos_version,
        current_tos_version=CURRENT_TOS_VERSION,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Push tokens (mobile)
# ─────────────────────────────────────────────────────────────────────────────

class PushTokenRequest(BaseModel):
    token: str


@router.post("/me/push-token", status_code=status.HTTP_201_CREATED)
async def register_push_token(
    payload: PushTokenRequest,
    db: AsyncSession = Depends(get_db),
    auth_user: ClerkAuthUser = Depends(get_clerk_user),
):
    user_id = auth_user.user_id

    # Check if the token already exists
    result = await db.execute(
        select(UserPushToken).where(
            UserPushToken.user_id == user_id,
            UserPushToken.expo_push_token == payload.token
        )
    )
    existing_token = result.scalars().first()

    if not existing_token:
        # Check if the token format is valid expo token format
        if not payload.token.startswith("ExponentPushToken[") and not payload.token.startswith("ExpoPushToken["):
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid push token format")

        new_token = UserPushToken(user_id=user_id, expo_push_token=payload.token)
        db.add(new_token)
        await db.commit()

    return {"status": "ok"}
