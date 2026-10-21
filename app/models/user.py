import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Boolean, Enum, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.activity_log import ActivityLog
    from app.models.kandang import Kandang
    from app.models.notification import Notification


class UserRole(str, PyEnum):
    """User roles enumeration."""
    ADMIN = "admin"
    PEMILIK = "pemilik"
    PETERNAK = "peternak"


class User(Base):
    """User model for authentication and authorization."""
    
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole),
        nullable=False,
        default=UserRole.PETERNAK,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    
    # For peternak: which pemilik they belong to
    pemilik_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Who created this user (admin)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Refresh token for token refresh
    refresh_token: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )
    refresh_token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    
    # Relationships
    # Peternak yang dimiliki oleh pemilik ini
    peternaks: Mapped[List["User"]] = relationship(
        "User",
        back_populates="pemilik",
        foreign_keys="User.pemilik_id",
    )
    # Pemilik dari peternak ini
    pemilik: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="peternaks",
        foreign_keys=[pemilik_id],
        remote_side="User.id",
    )
    
    # User yang membuat akun ini
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by_id],
        remote_side="User.id",
    )
    
    # Activity logs
    activity_logs: Mapped[List["ActivityLog"]] = relationship(
        "ActivityLog",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    
    # Kandang yang dimiliki (untuk pemilik)
    kandangs: Mapped[List["Kandang"]] = relationship(
        "Kandang",
        back_populates="pemilik",
        foreign_keys="Kandang.pemilik_id",
    )
    
    # Notifications
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role.value})>"
