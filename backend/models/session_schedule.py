import uuid
from datetime import datetime, time, date
from typing import Optional
from sqlalchemy import String, Numeric, Boolean, Integer, Date, Time
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class SessionSchedule(Base):
    __tablename__ = "session_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Session template — copied to TradingSession on auto-start
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    strategy: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_params: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    capital: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)  # "paper" | "alpaca_paper" | "alpaca_live"

    # Optional risk params
    stop_loss_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    take_profit_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    max_position_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)

    # Schedule config
    days_of_week: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[0,1,2,3,4]")
    start_time_et: Mapped[time] = mapped_column(Time(), nullable=False)
    stop_time_et: Mapped[Optional[time]] = mapped_column(Time(), nullable=True)  # None → 16:00 ET

    # Auto-stop conditions
    auto_stop_daily_loss_pct: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    auto_stop_max_trades: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)

    # State
    is_active: Mapped[bool] = mapped_column(Boolean(), nullable=False, default=True)
    last_triggered_date: Mapped[Optional[date]] = mapped_column(Date(), nullable=True)
    last_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_run_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
