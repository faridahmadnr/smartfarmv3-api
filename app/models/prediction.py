"""
Prediction Model - Hasil prediksi ML dari data sensor IoT
"""
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.kandang import Kandang
    from app.models.sensor_data import SensorData


class Prediction(Base):
    """Hasil prediksi ML — classification dan forecasting."""

    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    kandang_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kandangs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sensor_data_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sensor_data.id", ondelete="SET NULL"),
        nullable=True,
    )

    # "classification" atau "forecasting"
    type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # "ml" (Machine Learning) atau "dl" (Deep Learning)
    model_type: Mapped[str] = mapped_column(String(5), nullable=False, default="ml", server_default="ml", index=True)

    # Classification fields
    prediction: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="Normal / Abnormal"
    )
    confidence: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Confidence score 0-1"
    )

    # Forecasting fields
    predicted_death: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Jumlah kematian diprediksi"
    )
    raw_prediction: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Raw model output sebelum rounding"
    )

    # Input snapshot
    input_data: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="JSON: nilai sensor yang digunakan sebagai input"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    kandang: Mapped["Kandang"] = relationship("Kandang")
    sensor_data: Mapped[Optional["SensorData"]] = relationship("SensorData")

    def __repr__(self) -> str:
        return f"<Prediction {self.type}: {self.prediction or self.predicted_death}>"
