import uuid
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from database import AsyncSessionLocal
from models.price_history import PriceHistory

router = APIRouter()

@router.websocket("/ws/sessions/{session_id}")
async def websocket_session(websocket: WebSocket, session_id: uuid.UUID):
    await websocket.accept()
    last_timestamp = None
    try:
        while True:
            async with AsyncSessionLocal() as db:
                from models.trading_session import TradingSession
                session = await db.get(TradingSession, session_id)
                if not session or session.status == "closed":
                    await websocket.send_text(json.dumps({"type": "session_closed"}))
                    break

                result = await db.execute(
                    select(PriceHistory)
                    .where(PriceHistory.symbol == session.symbol)
                    .order_by(PriceHistory.timestamp.desc())
                    .limit(1)
                )
                latest = result.scalar_one_or_none()
                if latest and latest.timestamp != last_timestamp:
                    last_timestamp = latest.timestamp
                    await websocket.send_text(json.dumps({
                        "type": "price_update",
                        "symbol": session.symbol,
                        "close": float(latest.close),
                        "timestamp": str(latest.timestamp),
                    }))
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        pass
