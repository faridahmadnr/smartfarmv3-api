from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_token_expiry_seconds,
)
from app.services.user_service import UserService
from app.schemas.auth import TokenResponse


class AuthService:
    """Service for authentication operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_service = UserService(db)
    
    async def authenticate(
        self,
        username: str,
        password: str,
    ) -> Optional[User]:
        """Authenticate user with username/email and password."""
        user = await self.user_service.get_by_username_or_email(username)
        
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        if not verify_password(password, user.hashed_password):
            return None
        
        return user
    
    async def create_tokens(self, user: User) -> TokenResponse:
        """Create access and refresh tokens for a user."""
        # Create access token
        access_token = create_access_token(
            subject=str(user.id),
            role=user.role.value,
        )
        
        # Create refresh token
        refresh_token, refresh_expires = create_refresh_token(
            subject=str(user.id),
        )
        
        # Store refresh token in database
        await self.user_service.update_refresh_token(
            user=user,
            refresh_token=refresh_token,
            expires_at=refresh_expires,
        )
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=get_token_expiry_seconds(),
        )
    
    async def refresh_tokens(self, refresh_token: str) -> Optional[TokenResponse]:
        """Refresh tokens using a valid refresh token."""
        # Verify the refresh token
        payload = verify_token(refresh_token, token_type="refresh")
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        # Get user from database
        user = await self.user_service.get_by_id(user_id)
        if not user or not user.is_active:
            return None
        
        # Verify the refresh token matches what's stored
        if user.refresh_token != refresh_token:
            return None
        
        # Note: No expiry check - sessions never expire
        # Refresh tokens can only be invalidated via logout
        
        # Create new tokens
        return await self.create_tokens(user)
    
    async def logout(self, user: User) -> bool:
        """Logout user by invalidating refresh token."""
        await self.user_service.update_refresh_token(
            user=user,
            refresh_token=None,
            expires_at=None,
        )
        return True
    
    async def change_password(
        self,
        user: User,
        old_password: str,
        new_password: str,
    ) -> bool:
        """Change user password after verifying old password."""
        if not verify_password(old_password, user.hashed_password):
            return False
        
        await self.user_service.update_password(user, new_password)
        
        # Invalidate refresh token to force re-login
        await self.user_service.update_refresh_token(
            user=user,
            refresh_token=None,
            expires_at=None,
        )
        
        return True
