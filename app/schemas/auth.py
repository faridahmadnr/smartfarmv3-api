from typing import Optional
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.user import UserRole


class LoginRequest(BaseModel):
    """Schema for login request."""
    
    username: str = Field(..., description="Username or email")
    password: str = Field(..., description="Password")


class LoginUserInfo(BaseModel):
    """User info included in login response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: uuid.UUID
    email: str
    username: str
    full_name: str
    role: UserRole
    pemilik_id: Optional[uuid.UUID] = None


class TokenResponse(BaseModel):
    """Schema for token response."""
    
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiry in seconds")


class LoginResponse(BaseModel):
    """Schema for login response with user info and tokens."""
    
    user: LoginUserInfo
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiry in seconds")


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""
    
    refresh_token: str = Field(..., description="Refresh token")


class ChangePasswordRequest(BaseModel):
    """Schema for change password request."""
    
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password")
    confirm_password: str = Field(..., description="Confirm new password")


class TokenPayload(BaseModel):
    """Schema for JWT token payload."""
    
    sub: str  # user id
    exp: int  # expiration time
    type: str  # 'access' or 'refresh'
    role: Optional[str] = None
