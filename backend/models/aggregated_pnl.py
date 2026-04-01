import uuid
from sqlalchemy import String, Numeric, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class AggregatedPnl(Base):
    __tablename__ = "aggregated_pnl"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False, index=True)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)
    period_start: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    period_end: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    total_pnl: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    num_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    num_wins: Mapped[int] = mapped_column(Integer, nullable=False)
    num_losses: Mapped[int] = mapped_column(Integer, nullable=False)
    win_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    starting_capital: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    ending_capital: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
