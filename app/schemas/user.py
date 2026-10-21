import uuid
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.user import UserRole


class UserBase(BaseModel):
    """Base user schema with common fields."""
    
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    full_name: str = Field(..., min_length=1, max_length=100, description="Full name")
    phone: Optional[str] = Field(default=None, max_length=20, description="Phone number")


class UserCreate(UserBase):
    """Schema for creating a new user."""
    
    password: str = Field(..., min_length=8, max_length=100, description="Password")
    role: UserRole = Field(..., description="User role")
    pemilik_id: Optional[uuid.UUID] = Field(
        default=None,
        description="ID of the pemilik (owner) for peternak users",
    )


class PeternakCreate(UserBase):
    """Schema for pemilik to create a peternak under their account."""
    
    password: str = Field(..., min_length=8, max_length=100, description="Password")


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    
    email: Optional[EmailStr] = Field(default=None, description="User email address")
    username: Optional[str] = Field(default=None, min_length=3, max_length=50)
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=20)
    is_active: Optional[bool] = Field(default=None, description="User active status")
    pemilik_id: Optional[uuid.UUID] = Field(default=None, description="Pemilik ID")


class UserResponse(BaseModel):
    """Schema for user response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    email: EmailStr
    username: str
    full_name: str
    phone: Optional[str] = None
    role: UserRole
    is_active: bool
    pemilik_id: Optional[uuid.UUID] = None
    created_by_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class UserWithPeternaks(UserResponse):
    """User response with list of peternaks (for pemilik)."""
    
    peternaks: List["UserResponse"] = []


class UserInDB(UserResponse):
    """User schema with hashed password for internal use."""
    
    hashed_password: str


# Update forward reference
UserWithPeternaks.model_rebuild()
