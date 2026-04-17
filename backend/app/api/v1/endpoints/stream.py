from fastapi import APIRouter, WebSocket

from app.api.v1.endpoints.instruments import stream_quotes as instrument_stream_quotes

router = APIRouter()


@router.websocket("/stream/quotes")
async def stream_quotes(websocket: WebSocket) -> None:
    await instrument_stream_quotes(websocket)
