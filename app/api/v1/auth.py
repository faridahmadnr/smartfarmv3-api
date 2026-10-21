from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    LoginResponse,
    LoginUserInfo,
    RefreshTokenRequest,
    ChangePasswordRequest,
)
from pydantic import BaseModel


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    phone: str | None = None
from app.schemas.base import BaseResponse, success_response, error_response
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.services.activity_log_service import ActivityLogService
from app.api.deps import get_current_user, get_request_info

router = APIRouter()


@router.post(
    "/login",
    response_model=BaseResponse[LoginResponse],
    summary="Login",
    description="Authenticate user and get access/refresh tokens with user info",
)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Login with username/email and password."""
    auth_service = AuthService(db)
    
    user = await auth_service.authenticate(
        username=login_data.username,
        password=login_data.password,
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username/email atau password salah",
        )
    
    tokens = await auth_service.create_tokens(user)
    
    # Create login response with user info
    login_response = LoginResponse(
        user=LoginUserInfo.model_validate(user),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
        expires_in=tokens.expires_in,
    )
    
    # Log activity
    request_info = await get_request_info(request)
    activity_service = ActivityLogService(db)
    await activity_service.log_action(
        user_id=user.id,
        action="login",
        resource="auth",
        request_info=request_info,
        details={"method": "password"},
    )
    
    return success_response(data=login_response, message="Login berhasil")


@router.post(
    "/refresh",
    response_model=BaseResponse[TokenResponse],
    summary="Refresh Token",
    description="Get new access token using refresh token",
)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token using refresh token."""
    auth_service = AuthService(db)
    
    tokens = await auth_service.refresh_tokens(refresh_data.refresh_token)
    
    if not tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token tidak valid atau sudah expired",
        )
    
    return success_response(data=tokens, message="Token berhasil di-refresh")


@router.get(
    "/me",
    response_model=BaseResponse[UserResponse],
    summary="Get Current User",
    description="Get current authenticated user information",
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    """Get current user information."""
    return success_response(
        data=UserResponse.model_validate(current_user),
        message="Data user berhasil diambil",
    )


@router.patch(
    "/me",
    response_model=BaseResponse[UserResponse],
    summary="Update Profile",
    description="Update current user's profile (full_name, phone)",
)
async def update_profile(
    data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile fields."""
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.phone is not None:
        # Simpan kosong string sebagai NULL
        current_user.phone = data.phone.strip() or None
    await db.commit()
    await db.refresh(current_user)
    return success_response(
        data=UserResponse.model_validate(current_user),
        message="Profil berhasil diperbarui",
    )


@router.post(
    "/change-password",
    response_model=BaseResponse,
    summary="Change Password",
    description="Change current user's password",
)
async def change_password(
    request: Request,
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change current user's password."""
    # Validate password confirmation
    if password_data.new_password != password_data.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password baru dan konfirmasi tidak cocok",
        )
    
    auth_service = AuthService(db)
    
    success = await auth_service.change_password(
        user=current_user,
        old_password=password_data.old_password,
        new_password=password_data.new_password,
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password lama salah",
        )
    
    # Log activity
    request_info = await get_request_info(request)
    activity_service = ActivityLogService(db)
    await activity_service.log_action(
        user_id=current_user.id,
        action="change_password",
        resource="auth",
        request_info=request_info,
    )
    
    return success_response(message="Password berhasil diubah. Silakan login kembali.")


@router.post(
    "/logout",
    response_model=BaseResponse,
    summary="Logout",
    description="Logout and invalidate refresh token",
)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout user and invalidate refresh token."""
    auth_service = AuthService(db)
    await auth_service.logout(current_user)
    
    # Log activity
    request_info = await get_request_info(request)
    activity_service = ActivityLogService(db)
    await activity_service.log_action(
        user_id=current_user.id,
        action="logout",
        resource="auth",
        request_info=request_info,
    )
    
    return success_response(message="Logout berhasil")
