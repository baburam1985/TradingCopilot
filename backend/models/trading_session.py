import uuid
from sqlalchemy import String, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class TradingSession(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    strategy: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    starting_capital: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)  # "paper" or "live"
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="active")
    created_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    closed_at: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
