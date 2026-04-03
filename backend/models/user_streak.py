import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class UserStreak(Base):
    """Singleton-style table (single-user app). Only one row expected."""

    __tablename__ = "user_streaks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Current consecutive trading-day streak (weekends/holidays do not break it)
    current_streak: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    # Best streak ever
    longest_streak: Mapped[int] = mapped_column(Integer(), nullable=False, default=0)
    # Last calendar date (YYYY-MM-DD) that counted toward the streak
    last_trading_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Milestone badges earned: list of {"badge": str, "earned_at": ISO, "streak": int}
    # Milestones at streaks 5, 10, 30, 60
    milestone_badges: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
