import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Numeric, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class CloseSummary(Base):
    __tablename__ = "close_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # When this summary was generated
    generated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    # Trading date (YYYY-MM-DD as string for simplicity)
    trading_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # Core performance metrics
    total_pnl: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    trade_count: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    win_rate: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    max_drawdown_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=0)

    # Pattern matching analysis: which patterns fired and their outcomes
    # Structure: [{"pattern": str, "fired": bool, "expected": str, "actual": str, "outcome_met": bool}]
    pattern_analysis: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Tomorrow setup preview: top 3 signals expected
    # Structure: [{"signal": str, "strategy": str, "confidence": float}]
    tomorrow_preview: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
