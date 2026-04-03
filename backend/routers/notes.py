import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from database import get_db
from models.paper_trade import PaperTrade
from models.trade_note import TradeNote

router = APIRouter()


class CreateNoteRequest(BaseModel):
    body: str = ""
    tags: List[str] = []


@router.post("/{trade_id}/notes", status_code=201)
async def create_note(
    trade_id: uuid.UUID,
    req: CreateNoteRequest,
    db: AsyncSession = Depends(get_db),
):
    trade = await db.get(PaperTrade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    note = TradeNote(
        trade_id=trade_id,
        body=req.body,
        tags=req.tags,
        created_at=datetime.now(timezone.utc),
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@router.get("/{trade_id}/notes")
async def list_notes(trade_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    trade = await db.get(PaperTrade, trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    result = await db.execute(
        select(TradeNote)
        .where(TradeNote.trade_id == trade_id)
        .order_by(TradeNote.created_at.asc())
    )
    return result.scalars().all()


@router.delete("/{trade_id}/notes/{note_id}", status_code=204)
async def delete_note(
    trade_id: uuid.UUID,
    note_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    note = await db.get(TradeNote, note_id)
    if not note or note.trade_id != trade_id:
        raise HTTPException(status_code=404, detail="Note not found")
    await db.delete(note)
    await db.commit()
