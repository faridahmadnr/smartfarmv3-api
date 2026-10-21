import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import Integer, String, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.kandang import Kandang
    from app.models.user import User


class DeathReport(Base):
    __tablename__ = "death_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    kandang_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kandangs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    count: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    reported_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    kandang: Mapped["Kandang"] = relationship("Kandang")
    reporter: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reported_by])

    __table_args__ = (
        Index("ix_death_reports_kandang_timestamp", "kandang_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<DeathReport kandang={self.kandang_id} count={self.count}>"
