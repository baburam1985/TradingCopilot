import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    strategy: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    alert_threshold: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    notify_email: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=False)
    email_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_signal: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    last_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    last_evaluated_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
