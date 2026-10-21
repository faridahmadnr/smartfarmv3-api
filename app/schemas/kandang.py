import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class LatestSensorSnapshot(BaseModel):
    """Snapshot ringkas sensor terbaru — disertakan di KandangResponse."""
    suhu: float
    kelembaban: float
    amoniak: float
    populasi: Optional[int] = None
    death: int = 0
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class KandangBase(BaseModel):
    """Base kandang schema."""
    
    nama: str = Field(..., min_length=1, max_length=100, description="Nama kandang")
    kode: str = Field(..., min_length=1, max_length=20, description="Kode unik kandang")
    lokasi: Optional[str] = Field(default=None, max_length=255, description="Lokasi")
    kapasitas: Optional[int] = Field(default=None, ge=0, description="Kapasitas kandang")
    deskripsi: Optional[str] = Field(default=None, description="Deskripsi kandang")


class KandangCreate(KandangBase):
    """Schema for creating kandang."""
    
    pemilik_id: uuid.UUID = Field(..., description="ID pemilik kandang")


class KandangUpdate(BaseModel):
    """Schema for updating kandang."""

    nama: Optional[str] = Field(default=None, min_length=1, max_length=100)
    lokasi: Optional[str] = Field(default=None, max_length=255)
    kapasitas: Optional[int] = Field(default=None, ge=0)
    deskripsi: Optional[str] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)
    tanggal_mulai_siklus: Optional[datetime] = Field(default=None, description="Tanggal mulai siklus panen. Set untuk reset hari_ke ke 1.")


class KandangResponse(BaseModel):
    """Schema for kandang response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    nama: str
    kode: str
    lokasi: Optional[str] = None
    kapasitas: Optional[int] = None
    deskripsi: Optional[str] = None
    is_active: bool
    pemilik_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    # Include pemilik info
    pemilik_name: Optional[str] = None

    tanggal_mulai_siklus: Optional[datetime] = None

    # Latest sensor data (untuk stats card di dashboard)
    latest_sensor: Optional[LatestSensorSnapshot] = None
