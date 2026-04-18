from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel

from app.api.deps import get_db, require_auth, get_auth
from app.models.user import UserPushToken

router = APIRouter()

class PushTokenRequest(BaseModel):
    token: str

@router.post("/me/push-token", status_code=status.HTTP_201_CREATED)
async def register_push_token(
    payload: PushTokenRequest,
    db: AsyncSession = Depends(get_db),
    auth_data: dict = Depends(get_auth),
):
    user_id = auth_data["sub"]
    
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
