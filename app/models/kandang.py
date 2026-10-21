import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, func, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.sensor_data import SensorData
    from app.models.notification import Notification


class Kandang(Base):
    """Kandang (cage/barn) model for farm management."""
    
    __tablename__ = "kandangs"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    nama: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    kode: Mapped[str] = mapped_column(
        String(20),
        unique=True,
        index=True,
        nullable=False,
    )
    lokasi: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    kapasitas: Mapped[Optional[int]] = mapped_column(
        nullable=True,
    )
    deskripsi: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    tanggal_mulai_siklus: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Owner of the kandang
    pemilik_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
    pemilik: Mapped["User"] = relationship(
        "User",
        back_populates="kandangs",
        foreign_keys=[pemilik_id],
    )
    sensor_data: Mapped[list["SensorData"]] = relationship(
        "SensorData",
        back_populates="kandang",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="kandang",
    )
    
    def __repr__(self) -> str:
        return f"<Kandang {self.kode}: {self.nama}>"
