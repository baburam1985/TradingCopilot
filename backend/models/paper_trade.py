import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class PaperTrade(Base):
    __tablename__ = "paper_trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(4), nullable=False)  # "buy" or "sell"
    signal_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    price_at_signal: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    timestamp_open: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    timestamp_close: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    price_at_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=True)
    pnl: Mapped[float] = mapped_column(Numeric(12, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="open")
