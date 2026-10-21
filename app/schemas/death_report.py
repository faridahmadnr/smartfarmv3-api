import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class DeathReportCreate(BaseModel):
    count: int = Field(..., ge=1, description="Number of deaths to report")
    notes: Optional[str] = Field(default=None, max_length=500)
    timestamp: Optional[datetime] = Field(default=None, description="Defaults to now if not provided")

    model_config = ConfigDict(
        json_schema_extra={"example": {"count": 3, "notes": "Ditemukan pagi hari"}}
    )


class DeathReportResponse(BaseModel):
    id: uuid.UUID
    kandang_id: uuid.UUID
    count: int
    notes: Optional[str]
    timestamp: datetime
    reported_by: Optional[uuid.UUID]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DeathReportListResponse(BaseModel):
    items: List[DeathReportResponse]
    total: int
    page: int
    per_page: int
