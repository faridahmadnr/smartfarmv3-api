import uuid
import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class DailyLogCreate(BaseModel):
    date: Optional[datetime.date] = Field(default=None, description="Defaults to today if not provided")
    pakan: Optional[float] = Field(default=None, ge=0, description="Total feed (kg)")
    minum: Optional[float] = Field(default=None, ge=0, description="Total water (liter)")
    populasi: Optional[int] = Field(default=None, ge=1, description="Current population")
    bobot: Optional[float] = Field(default=None, ge=0, description="Average weight sample (gram)")
    notes: Optional[str] = Field(default=None, max_length=1000)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pakan": 180.5,
                "minum": 320.0,
                "populasi": 7980,
                "bobot": None,
                "notes": "Kondisi kandang baik"
            }
        }
    )


class DailyLogResponse(BaseModel):
    id: uuid.UUID
    kandang_id: uuid.UUID
    date: datetime.date
    pakan: Optional[float]
    minum: Optional[float]
    populasi: Optional[int]
    bobot: Optional[float]
    notes: Optional[str]
    recorded_by: Optional[uuid.UUID]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class DailyLogListResponse(BaseModel):
    items: List[DailyLogResponse]
    total: int
    page: int
    per_page: int
