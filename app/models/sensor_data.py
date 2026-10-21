"""
SensorData Model - IoT sensor readings for kandang monitoring
"""
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.kandang import Kandang
    from app.models.user import User


class SensorData(Base):
    """IoT sensor reading model for farm monitoring."""
    
    __tablename__ = "sensor_data"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    
    # Foreign key to kandang
    kandang_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kandangs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Recording timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    
    # === Auto-captured by IoT sensors ===
    hari_ke: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Day number in cultivation cycle"
    )
    suhu: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Temperature in Celsius"
    )
    kelembaban: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Humidity percentage"
    )
    amoniak: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Ammonia level in ppm"
    )
    
    # === Manually input data ===
    pakan: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Feed per chicken (gram)"
    )
    minum: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Water consumption per chicken (ml)"
    )
    bobot: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Average chicken weight (gram)"
    )
    populasi: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Current chicken population"
    )
    
    # Death count for this interval
    death: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Number of deaths in this interval"
    )
    
    # Who recorded this data (if manually input)
    recorded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
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
    kandang: Mapped["Kandang"] = relationship(
        "Kandang",
        back_populates="sensor_data",
    )
    recorded_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[recorded_by],
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index('ix_sensor_data_kandang_timestamp', 'kandang_id', 'timestamp'),
    )
    
    def __repr__(self) -> str:
        return f"<SensorData {self.kandang_id} @ {self.timestamp}>"
