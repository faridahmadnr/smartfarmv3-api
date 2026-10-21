import uuid
from datetime import datetime
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict

from app.models.activity_log import Platform


class ActivityLogBase(BaseModel):
    """Base activity log schema."""
    
    action: str = Field(..., max_length=50, description="Action performed")
    resource: str = Field(..., max_length=50, description="Resource type")
    resource_id: Optional[uuid.UUID] = Field(default=None, description="Resource ID")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional details")
    platform: Platform = Field(default=Platform.WEB, description="Platform")


class ActivityLogCreate(ActivityLogBase):
    """Schema for creating activity log."""
    
    user_id: uuid.UUID = Field(..., description="User ID")
    ip_address: Optional[str] = Field(default=None, description="IP address")
    user_agent: Optional[str] = Field(default=None, description="User agent")


class ActivityLogResponse(BaseModel):
    """Schema for activity log response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    user_id: uuid.UUID
    action: str
    resource: str
    resource_id: Optional[uuid.UUID] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    platform: Platform
    created_at: datetime
    
    # Include user info for admin view
    user_username: Optional[str] = None
    user_full_name: Optional[str] = None
