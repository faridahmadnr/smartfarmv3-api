import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.activity_log import ActivityLog, Platform
from app.models.user import User
from app.schemas.activity_log import ActivityLogCreate


class ActivityLogService:
    """Service for activity log operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self,
        user_id: uuid.UUID,
        action: str,
        resource: str,
        resource_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        platform: Platform = Platform.WEB,
    ) -> ActivityLog:
        """Create a new activity log entry."""
        log = ActivityLog(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            platform=platform,
        )
        
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)
        
        return log
    
    async def get_list(
        self,
        page: int = 1,
        per_page: int = 10,
        user_id: Optional[uuid.UUID] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        platform: Optional[Platform] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[List[ActivityLog], int]:
        """Get paginated list of activity logs with filters."""
        query = select(ActivityLog).options(joinedload(ActivityLog.user))
        count_query = select(func.count(ActivityLog.id))
        
        # Apply filters
        if user_id:
            query = query.where(ActivityLog.user_id == user_id)
            count_query = count_query.where(ActivityLog.user_id == user_id)
        
        if action:
            query = query.where(ActivityLog.action == action)
            count_query = count_query.where(ActivityLog.action == action)
        
        if resource:
            query = query.where(ActivityLog.resource == resource)
            count_query = count_query.where(ActivityLog.resource == resource)
        
        if platform:
            query = query.where(ActivityLog.platform == platform)
            count_query = count_query.where(ActivityLog.platform == platform)
        
        if start_date:
            query = query.where(ActivityLog.created_at >= start_date)
            count_query = count_query.where(ActivityLog.created_at >= start_date)
        
        if end_date:
            query = query.where(ActivityLog.created_at <= end_date)
            count_query = count_query.where(ActivityLog.created_at <= end_date)
        
        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()
        
        # Apply pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page).order_by(ActivityLog.created_at.desc())
        
        result = await self.db.execute(query)
        logs = result.scalars().unique().all()
        
        return list(logs), total
    
    async def get_user_logs(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        per_page: int = 10,
    ) -> tuple[List[ActivityLog], int]:
        """Get activity logs for a specific user."""
        return await self.get_list(
            page=page,
            per_page=per_page,
            user_id=user_id,
        )
    
    async def log_action(
        self,
        user_id: uuid.UUID,
        action: str,
        resource: str,
        request_info: Optional[Dict[str, Any]] = None,
        resource_id: Optional[uuid.UUID] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> ActivityLog:
        """Helper method to log an action with request info."""
        ip_address = None
        user_agent = None
        platform = Platform.WEB
        
        if request_info:
            ip_address = request_info.get("ip_address")
            user_agent = request_info.get("user_agent")
            platform_str = request_info.get("platform", "web").lower()
            if platform_str == "mobile":
                platform = Platform.MOBILE
            elif platform_str == "api":
                platform = Platform.API
        
        return await self.create(
            user_id=user_id,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            platform=platform,
        )
