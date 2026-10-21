"""
Notification Model - Real-time alerts for ML predictions
"""
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from enum import Enum

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, func, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.kandang import Kandang


class NotificationType(str, Enum):
    """Types of notifications."""
    ABNORMAL_CLASSIFICATION = "abnormal_classification"
    DEATH_FORECAST = "death_forecast"
    SYSTEM = "system"


class Notification(Base):
    """Notification model for ML prediction alerts."""
    
    __tablename__ = "notifications"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Recipient user
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Related kandang (optional)
    kandang_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kandangs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Notification content
    type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    
    # Additional data (JSON serializable)
    data: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON string with additional notification data"
    )
    
    # Status
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="notifications",
    )
    kandang: Mapped[Optional["Kandang"]] = relationship(
        "Kandang",
        back_populates="notifications",
    )
    
    def __repr__(self) -> str:
        return f"<Notification {self.type}: {self.title[:30]}>"
