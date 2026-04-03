import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, Index
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class AlertEvent(Base):
    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # trade_executed | stop_loss | take_profit | daily_loss_limit | session_ended
    level: Mapped[str] = mapped_column(String(10), nullable=False)
    # info | warning | danger
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    delivered_email: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_alert_events_session_created", "session_id", "created_at"),
    )
