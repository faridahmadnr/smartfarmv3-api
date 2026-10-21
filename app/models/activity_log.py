import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Enum, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Platform(str, PyEnum):
    """Platform enumeration for activity logging."""
    WEB = "web"
    MOBILE = "mobile"
    API = "api"


class ActivityLog(Base):
    """Activity log model for tracking user actions."""
    
    __tablename__ = "activity_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Action details
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # e.g., 'login', 'logout', 'create_user', 'update_kandang'
    
    resource: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # e.g., 'auth', 'user', 'kandang', 'prediction'
    
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    
    # Additional details as JSON
    details: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    
    # Request info
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),  # IPv6 max length
        nullable=True,
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    platform: Mapped[Platform] = mapped_column(
        Enum(Platform),
        nullable=False,
        default=Platform.WEB,
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
        back_populates="activity_logs",
    )
    
    def __repr__(self) -> str:
        return f"<ActivityLog {self.action} by {self.user_id}>"
