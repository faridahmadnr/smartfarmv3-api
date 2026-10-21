"""
Notification Schemas - Request and Response models for notifications
"""
import uuid
from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, Field, ConfigDict


class NotificationResponse(BaseModel):
    """Response schema for a single notification."""
    id: uuid.UUID
    user_id: uuid.UUID
    kandang_id: Optional[uuid.UUID]
    type: str
    title: str
    message: str
    data: Optional[str]
    is_read: bool
    read_at: Optional[datetime]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class NotificationListResponse(BaseModel):
    """Response schema for list of notifications."""
    items: List[NotificationResponse]
    total: int
    unread_count: int
    page: int = 1
    total_pages: int = 1
    limit: int = 20


class NotificationCreate(BaseModel):
    """Schema for creating a notification (internal use)."""
    user_id: uuid.UUID
    kandang_id: Optional[uuid.UUID] = None
    type: str
    title: str
    message: str
    data: Optional[str] = None


class UnreadCountResponse(BaseModel):
    """Response schema for unread count."""
    unread_count: int


class MarkReadResponse(BaseModel):
    """Response schema after marking as read."""
    id: uuid.UUID
    is_read: bool
    read_at: datetime
