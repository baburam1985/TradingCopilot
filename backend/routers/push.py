import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.push_subscription import PushSubscription
from notifications.push import is_push_configured

router = APIRouter()


class PushSubscribeRequest(BaseModel):
    session_id: uuid.UUID
    endpoint: str
    p256dh: str
    auth: str


class PushUnsubscribeRequest(BaseModel):
    session_id: uuid.UUID
    endpoint: str


@router.post("/subscribe", status_code=201)
async def subscribe(body: PushSubscribeRequest, db: AsyncSession = Depends(get_db)):
    """Store a browser push subscription for a trading session."""
    # Upsert: remove any existing subscription with the same endpoint first
    await db.execute(
        delete(PushSubscription).where(PushSubscription.endpoint == body.endpoint)
    )
    sub = PushSubscription(
        id=uuid.uuid4(),
        session_id=body.session_id,
        endpoint=body.endpoint,
        p256dh=body.p256dh,
        auth=body.auth,
        created_at=datetime.now(timezone.utc),
    )
    db.add(sub)
    await db.commit()
    return {"status": "subscribed", "id": str(sub.id)}


@router.delete("/unsubscribe", status_code=200)
async def unsubscribe(body: PushUnsubscribeRequest, db: AsyncSession = Depends(get_db)):
    """Remove a browser push subscription."""
    result = await db.execute(
        delete(PushSubscription)
        .where(PushSubscription.session_id == body.session_id)
        .where(PushSubscription.endpoint == body.endpoint)
        .returning(PushSubscription.id)
    )
    deleted = result.fetchone()
    if deleted is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    await db.commit()
    return {"status": "unsubscribed"}


@router.get("/vapid-public-key")
async def get_vapid_public_key():
    """Return the VAPID public key for the browser to use when subscribing."""
    import os
    if not is_push_configured():
        raise HTTPException(status_code=503, detail="Push notifications not configured")
    return {"publicKey": os.environ["VAPID_PUBLIC_KEY"]}
