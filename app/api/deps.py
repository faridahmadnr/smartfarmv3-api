import uuid
from typing import Optional, Dict, Any

from fastapi import Depends, HTTPException, status, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.kandang import Kandang
from app.services.user_service import UserService
from app.core.security import verify_token
from app.config import get_settings


security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user from JWT token."""
    token = credentials.credentials
    
    payload = verify_token(token, token_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid atau sudah expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_service = UserService(db)
    user = await user_service.get_by_id(uuid.UUID(user_id))
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User tidak ditemukan",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User tidak aktif",
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User tidak aktif",
        )
    return current_user


def require_roles(*roles: UserRole):
    """Dependency to require specific roles."""
    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Akses ditolak. Role yang dibutuhkan: {', '.join([r.value for r in roles])}",
            )
        return current_user
    return role_checker


def require_admin():
    """Dependency to require admin role."""
    return require_roles(UserRole.ADMIN)


def require_pemilik_or_admin():
    """Dependency to require pemilik or admin role."""
    return require_roles(UserRole.ADMIN, UserRole.PEMILIK)


async def get_iot_auth(
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> str:
    """Validate IoT device API key from X-API-Key header."""
    settings = get_settings()
    if x_api_key != settings.iot_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid IoT API key",
        )
    return x_api_key


async def get_single_kandang(db: AsyncSession = Depends(get_db)) -> Kandang:
    result = await db.execute(
        select(Kandang).where(Kandang.is_active == True).limit(1)
    )
    kandang = result.scalar_one_or_none()
    if not kandang:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kandang tidak ditemukan",
        )
    return kandang


async def get_request_info(request: Request) -> Dict[str, Any]:
    """Extract request information for logging."""
    # Get client IP
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip_address = forwarded.split(",")[0].strip()
    else:
        ip_address = request.client.host if request.client else None
    
    # Get user agent
    user_agent = request.headers.get("User-Agent")
    
    # Determine platform from custom header or user agent
    platform = request.headers.get("X-Platform", "web").lower()
    if "mobile" in (user_agent or "").lower() and platform == "web":
        platform = "mobile"
    
    return {
        "ip_address": ip_address,
        "user_agent": user_agent,
        "platform": platform,
    }
