from __future__ import annotations

import logging
from typing import Any, Iterable

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

import httpx

logger = logging.getLogger(__name__)


async def send_push_notifications(
    tokens: Iterable[str],
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    deduped_tokens = list(dict.fromkeys(token for token in tokens if token))
    payload = [
        {
            "to": token,
            "sound": "default",
            "title": title,
            "body": body,
            "data": data or {},
        }
        for token in deduped_tokens
    ]

    if not payload:
        return {"sent": 0, "tickets": []}

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            EXPO_PUSH_URL,
            json=payload,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        response.raise_for_status()
        result = response.json()
        logger.info("Expo push accepted %s notifications", len(payload))
        return {"sent": len(payload), "tickets": result.get("data", [])}


async def send_expo_push(
    tokens: list[str], title: str, body: str, data: dict[str, Any] | None = None
) -> dict[str, Any]:
    return await send_push_notifications(tokens=tokens, title=title, body=body, data=data)
