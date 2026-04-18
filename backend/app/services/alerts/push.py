import httpx
from typing import List

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

async def send_expo_push(tokens: List[str], title: str, body: str, data: dict = None):
    payload = []
    for token in tokens:
        payload.append({
            "to": token,
            "sound": "default",
            "title": title,
            "body": body,
            "data": data or {}
        })
    
    if not payload:
        return None

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(EXPO_PUSH_URL, json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            # Handle or log the error
            print(f"Failed to send push notification: {e}")
            return None
