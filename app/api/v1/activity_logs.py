import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.activity_log import Platform
from app.schemas.activity_log import ActivityLogResponse
from app.schemas.base import PaginatedResponse, paginated_response
from app.services.activity_log_service import ActivityLogService
from app.api.deps import get_current_user, require_admin

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[ActivityLogResponse],
    summary="List Activity Logs",
    description="Get paginated list of activity logs (Admin only)",
)
async def list_activity_logs(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    user_id: Optional[uuid.UUID] = Query(None, description="Filter by user ID"),
    action: Optional[str] = Query(None, description="Filter by action"),
    resource: Optional[str] = Query(None, description="Filter by resource"),
    platform: Optional[Platform] = Query(None, description="Filter by platform"),
    start_date: Optional[datetime] = Query(None, description="Filter from date"),
    end_date: Optional[datetime] = Query(None, description="Filter to date"),
    current_user: User = Depends(require_admin()),
    db: AsyncSession = Depends(get_db),
):
    """Get all activity logs with filters. Admin only."""
    activity_service = ActivityLogService(db)
    
    logs, total = await activity_service.get_list(
        page=page,
        per_page=per_page,
        user_id=user_id,
        action=action,
        resource=resource,
        platform=platform,
        start_date=start_date,
        end_date=end_date,
    )
    
    log_responses = []
    for log in logs:
        response = ActivityLogResponse.model_validate(log)
        # Add user info
        if log.user:
            response.user_username = log.user.username
            response.user_full_name = log.user.full_name
        log_responses.append(response)
    
    return paginated_response(
        data=log_responses,
        total=total,
        page=page,
        per_page=per_page,
        message="Daftar activity log berhasil diambil",
    )


@router.get(
    "/me",
    response_model=PaginatedResponse[ActivityLogResponse],
    summary="Get My Activity Logs",
    description="Get current user's activity logs",
)
async def get_my_activity_logs(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's activity logs."""
    activity_service = ActivityLogService(db)
    
    logs, total = await activity_service.get_user_logs(
        user_id=current_user.id,
        page=page,
        per_page=per_page,
    )
    
    log_responses = [ActivityLogResponse.model_validate(log) for log in logs]
    
    return paginated_response(
        data=log_responses,
        total=total,
        page=page,
        per_page=per_page,
        message="Daftar activity log berhasil diambil",
    )
