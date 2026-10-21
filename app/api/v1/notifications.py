"""
Notification API Routes - Notification history and WebSocket endpoints
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt, JWTError

from app.database import get_db
from app.models.user import User
from app.config import get_settings
from app.schemas.base import BaseResponse, success_response
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    UnreadCountResponse,
    MarkReadResponse,
)
from app.services.notification_service import NotificationService, manager
from app.api.deps import get_current_user

router = APIRouter()
settings = get_settings()


@router.get(
    "",
    response_model=BaseResponse[NotificationListResponse],
    summary="Get Notifications",
    description="Get user's notification history",
)
async def get_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=20, ge=1, le=100),
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get notification history for the current user.
    """
    service = NotificationService(db)
    offset = (page - 1) * limit
    items, total, unread_count = await service.get_by_user(
        current_user.id, unread_only, limit, offset
    )
    
    import math
    total_pages = max(1, math.ceil(total / limit))
    return success_response(
        data=NotificationListResponse(
            items=[NotificationResponse.model_validate(item) for item in items],
            total=total,
            unread_count=unread_count,
            page=page,
            total_pages=total_pages,
            limit=limit,
        ),
        message="Notifikasi berhasil diambil",
    )


@router.get(
    "/unread-count",
    response_model=BaseResponse[UnreadCountResponse],
    summary="Get Unread Count",
    description="Get count of unread notifications",
)
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the number of unread notifications.
    """
    service = NotificationService(db)
    count = await service.get_unread_count(current_user.id)
    
    return success_response(
        data=UnreadCountResponse(unread_count=count),
        message=f"{count} notifikasi belum dibaca",
    )


@router.put(
    "/{notification_id}/read",
    response_model=BaseResponse[MarkReadResponse],
    summary="Mark as Read",
    description="Mark a notification as read",
)
async def mark_as_read(
    notification_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a specific notification as read.
    """
    service = NotificationService(db)
    notification = await service.mark_as_read(notification_id, current_user.id)
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notifikasi tidak ditemukan"
        )
    
    return success_response(
        data=MarkReadResponse(
            id=notification.id,
            is_read=notification.is_read,
            read_at=notification.read_at,
        ),
        message="Notifikasi ditandai sudah dibaca",
    )


@router.put(
    "/read-all",
    response_model=BaseResponse[dict],
    summary="Mark All as Read",
    description="Mark all notifications as read",
)
async def mark_all_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark all notifications as read for the current user.
    """
    service = NotificationService(db)
    count = await service.mark_all_as_read(current_user.id)
    
    return success_response(
        data={"marked_count": count},
        message=f"{count} notifikasi ditandai sudah dibaca",
    )


# WebSocket endpoint for real-time notifications
@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    WebSocket endpoint for real-time notification push.
    
    Connect with: ws://host/api/v1/notifications/ws?token=<jwt_token>
    
    Messages received will be JSON with format:
    {
        "type": "notification",
        "data": {
            "id": "...",
            "notification_type": "abnormal_classification" | "death_forecast",
            "title": "...",
            "message": "...",
            "kandang_id": "..." | null,
            "created_at": "..."
        }
    }
    """
    # Validate token
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            await websocket.accept()
            await websocket.close(code=4001, reason="Invalid token: no user")
            return
    except JWTError as e:
        print(f"🔒 WebSocket auth failed: {e}")
        await websocket.accept()
        await websocket.close(code=4001, reason="Invalid or expired token")
        return
    
    # Connect
    await manager.connect(websocket, user_id)
    
    try:
        # Keep connection alive and listen for client messages
        while True:
            data = await websocket.receive_text()
            # Handle ping/pong for keep-alive
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        print(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)
