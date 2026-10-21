import uuid
from datetime import datetime, date
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Integer, Float, String, DateTime, Date, ForeignKey, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.kandang import Kandang
    from app.models.user import User


class DailyLog(Base):
    __tablename__ = "daily_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    kandang_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kandangs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    pakan: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Total feed today (kg)")
    minum: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Total water today (liter)")
    populasi: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Current population")
    bobot: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Average weight sample (gram)")
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)

    recorded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    kandang: Mapped["Kandang"] = relationship("Kandang")
    recorder: Mapped[Optional["User"]] = relationship("User", foreign_keys=[recorded_by])

    __table_args__ = (
        UniqueConstraint("kandang_id", "date", name="uq_daily_log_kandang_date"),
    )

    def __repr__(self) -> str:
        return f"<DailyLog kandang={self.kandang_id} date={self.date}>"
