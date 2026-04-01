import uuid
from sqlalchemy import String, Numeric, BigInteger, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timestamp: Mapped[str] = mapped_column(TIMESTAMP(timezone=True), nullable=False, index=True)
    open: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)
    yahoo_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=True)
    alphavantage_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=True)
    finnhub_close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=True)
    outlier_flags: Mapped[dict] = mapped_column(JSONB, nullable=True)
    sources_available: Mapped[list] = mapped_column(ARRAY(String), nullable=False)
