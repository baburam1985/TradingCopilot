import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Date, Index
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class EventsCalendar(Base):
    __tablename__ = "events_calendar"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # earnings | fomc | cpi
    symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # NULL for macro events (fomc, cpi)
    event_date: Mapped[datetime] = mapped_column(Date(), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    fetched_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_events_calendar_symbol_date", "symbol", "event_date"),
        Index("ix_events_calendar_type_date", "event_type", "event_date"),
    )
