"""
Sensor Data Schemas - Request and Response models for sensor data CRUD
"""
import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


# ============================================
# REQUEST SCHEMAS
# ============================================

class SensorDataCreate(BaseModel):
    timestamp: datetime = Field(..., description="Recording timestamp")
    hari_ke: int = Field(..., ge=1, description="Day number in cycle")
    suhu: float = Field(..., ge=0, le=60, description="Temperature (°C)")
    kelembaban: float = Field(..., ge=0, le=100, description="Humidity (%)")
    amoniak: float = Field(..., ge=0, description="Ammonia level (ppm)")
    pakan: Optional[float] = Field(default=None, ge=0)
    minum: Optional[float] = Field(default=None, ge=0)
    bobot: Optional[float] = Field(default=None, ge=0)
    populasi: Optional[int] = Field(default=None, ge=1)
    death: int = Field(default=0, ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2026-01-19T10:30:00+07:00",
                "hari_ke": 5,
                "suhu": 28.5,
                "kelembaban": 75.0,
                "amoniak": 3.5,
                "pakan": 150,
                "minum": 350,
                "bobot": 58,
                "populasi": 8000,
                "death": 0
            }
        }
    )


class SensorDataIoTCreate(BaseModel):
    """Schema for IoT device submissions (ESP32). Uses English field names."""
    temperature: float = Field(..., ge=0, le=60, description="Suhu (°C)")
    humidity: float = Field(..., ge=0, le=100, description="Kelembaban (%)")
    ammonia: float = Field(..., ge=0, description="Amonia (ppm)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "temperature": 28.5,
                "humidity": 75.0,
                "ammonia": 3.5,
            }
        }
    )


class SensorDataManualUpdate(BaseModel):
    """Schema for updating manual fields only."""
    pakan: Optional[float] = Field(default=None, ge=0, description="Feed per chicken (gram)")
    minum: Optional[float] = Field(default=None, ge=0, description="Water per chicken (ml)")
    bobot: Optional[float] = Field(default=None, ge=0, description="Average weight (gram)")
    populasi: Optional[int] = Field(default=None, ge=1, description="Population count")
    death: Optional[int] = Field(default=None, ge=0, description="Deaths in this interval")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pakan": 155,
                "minum": 360,
                "bobot": 62,
                "populasi": 7995,
                "death": 2
            }
        }
    )


# ============================================
# RESPONSE SCHEMAS
# ============================================

class SensorDataResponse(BaseModel):
    """Response schema for a single sensor data record."""
    id: uuid.UUID
    kandang_id: uuid.UUID
    timestamp: datetime
    hari_ke: int
    suhu: float
    kelembaban: float
    amoniak: float
    pakan: Optional[float]
    minum: Optional[float]
    bobot: Optional[float]
    populasi: Optional[int]
    death: int
    recorded_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SensorDataListResponse(BaseModel):
    """Response schema for list of sensor data."""
    items: List[SensorDataResponse]
    total: int
    page: int
    page_size: int


class SensorDataStats(BaseModel):
    """Statistical summary of sensor data."""
    kandang_id: uuid.UUID
    period_start: datetime
    period_end: datetime
    total_readings: int
    avg_suhu: float
    avg_kelembaban: float
    avg_amoniak: float
    total_deaths: int
    latest_populasi: Optional[int]
