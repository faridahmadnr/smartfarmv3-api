import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.schemas.base import (
    BaseResponse,
    PaginatedResponse,
    success_response,
    paginated_response,
)
from app.services.user_service import UserService
from app.services.activity_log_service import ActivityLogService
from app.api.deps import (
    get_current_user,
    require_admin,
    get_request_info,
)

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[UserResponse],
    summary="List Users",
    description="Get paginated list of users (Admin only)",
)
async def list_users(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    role: Optional[UserRole] = Query(None, description="Filter by role"),
    pemilik_id: Optional[uuid.UUID] = Query(None, description="Filter by pemilik"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by name/email/username"),
    current_user: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    """Get list of users with pagination and filters."""
    user_service = UserService(db)
    
    users, total = await user_service.get_list(
        page=page,
        per_page=per_page,
        role=role,
        pemilik_id=pemilik_id,
        is_active=is_active,
        search=search,
    )
    
    user_responses = [UserResponse.model_validate(u) for u in users]
    
    return paginated_response(
        data=user_responses,
        total=total,
        page=page,
        per_page=per_page,
        message="Daftar user berhasil diambil",
    )


@router.get(
    "/{user_id}",
    response_model=BaseResponse[UserResponse],
    summary="Get User",
    description="Get user by ID",
)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user by ID. Admin can view any user, others can only view themselves."""
    # Allow admin to view any user, others can only view themselves
    if current_user.role != UserRole.ADMIN and current_user.id != user_id:
        # Pemilik can view their peternaks
        if current_user.role == UserRole.PEMILIK:
            user_service = UserService(db)
            target_user = await user_service.get_by_id(user_id)
            if not target_user or target_user.pemilik_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Akses ditolak",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Akses ditolak",
            )
    
    user_service = UserService(db)
    user = await user_service.get_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User tidak ditemukan",
        )
    
    return success_response(
        data=UserResponse.model_validate(user),
        message="Data user berhasil diambil",
    )


@router.post(
    "",
    response_model=BaseResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create User",
    description="Create new user (Admin only). Pemilik and Peternak accounts must be created by Admin.",
)
async def create_user(
    request: Request,
    user_data: UserCreate,
    current_user: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user. Only admin can create users."""
    user_service = UserService(db)
    
    # Check if email already exists
    existing_email = await user_service.get_by_email(user_data.email)
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email sudah terdaftar",
        )
    
    # Check if username already exists
    existing_username = await user_service.get_by_username(user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username sudah terdaftar",
        )
    
    # Validate pemilik_id for peternak role
    if user_data.role == UserRole.PETERNAK:
        if not user_data.pemilik_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Peternak harus memiliki pemilik",
            )
        
        pemilik = await user_service.get_by_id(user_data.pemilik_id)
        if not pemilik or pemilik.role != UserRole.PEMILIK:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pemilik tidak valid",
            )
    
    # Create user
    user = await user_service.create(
        user_data=user_data,
        created_by_id=current_user.id,
    )
    
    # Log activity
    request_info = await get_request_info(request)
    activity_service = ActivityLogService(db)
    await activity_service.log_action(
        user_id=current_user.id,
        action="create_user",
        resource="user",
        resource_id=user.id,
        request_info=request_info,
        details={"role": user.role.value, "username": user.username},
    )
    
    return success_response(
        data=UserResponse.model_validate(user),
        message="User berhasil dibuat",
    )


@router.put(
    "/{user_id}",
    response_model=BaseResponse[UserResponse],
    summary="Update User",
    description="Update user data (Admin only)",
)
async def update_user(
    user_id: uuid.UUID,
    request: Request,
    user_data: UserUpdate,
    current_user: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    """Update user data. Only admin can update users."""
    user_service = UserService(db)
    
    user = await user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User tidak ditemukan",
        )
    
    # Check unique constraints if updating email/username
    if user_data.email and user_data.email != user.email:
        existing = await user_service.get_by_email(user_data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email sudah terdaftar",
            )
    
    if user_data.username and user_data.username != user.username:
        existing = await user_service.get_by_username(user_data.username)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username sudah terdaftar",
            )
    
    # Validate pemilik_id update
    if user_data.pemilik_id:
        pemilik = await user_service.get_by_id(user_data.pemilik_id)
        if not pemilik or pemilik.role != UserRole.PEMILIK:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pemilik tidak valid",
            )
    
    updated_user = await user_service.update(user, user_data)
    
    # Log activity
    request_info = await get_request_info(request)
    activity_service = ActivityLogService(db)
    await activity_service.log_action(
        user_id=current_user.id,
        action="update_user",
        resource="user",
        resource_id=user_id,
        request_info=request_info,
        details={"updated_fields": list(user_data.model_dump(exclude_unset=True).keys())},
    )
    
    return success_response(
        data=UserResponse.model_validate(updated_user),
        message="User berhasil diupdate",
    )


@router.delete(
    "/{user_id}",
    response_model=BaseResponse,
    summary="Delete User",
    description="Soft delete (deactivate) a user (Admin only)",
)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    """Soft delete (deactivate) a user. Only admin can delete users."""
    user_service = UserService(db)
    
    user = await user_service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User tidak ditemukan",
        )
    
    # Prevent deleting self
    if user.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tidak dapat menghapus akun sendiri",
        )
    
    await user_service.deactivate(user)
    
    # Log activity
    request_info = await get_request_info(request)
    activity_service = ActivityLogService(db)
    await activity_service.log_action(
        user_id=current_user.id,
        action="delete_user",
        resource="user",
        resource_id=user_id,
        request_info=request_info,
        details={"username": user.username},
    )
    
    return success_response(message="User berhasil dihapus")

