import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.kandang import Kandang
from app.schemas.kandang import KandangUpdate, KandangResponse
from app.schemas.base import BaseResponse, success_response
from app.services.kandang_service import KandangService
from app.services.activity_log_service import ActivityLogService
from app.api.deps import get_current_user, require_roles, get_request_info

router = APIRouter()


@router.get(
    "/me",
    response_model=BaseResponse[KandangResponse],
    summary="Get Kandang",
    description="Get detail kandang aktif",
)
async def get_my_kandang(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kandang_service = KandangService(db)
    result = await db.execute(
        select(Kandang)
        .options(selectinload(Kandang.pemilik))
        .where(Kandang.is_active == True)
        .limit(1)
    )
    kandang = result.scalar_one_or_none()
    if not kandang:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kandang tidak ditemukan")

    response = KandangResponse.model_validate(kandang)
    if kandang.pemilik:
        response.pemilik_name = kandang.pemilik.full_name
    response.latest_sensor = await kandang_service.get_latest_sensor(kandang.id)

    return success_response(data=response, message="Data kandang berhasil diambil")


@router.put(
    "/{kandang_id}",
    include_in_schema=False,
    response_model=BaseResponse[KandangResponse],
    summary="Update Kandang",
    description="Update kandang data",
)
async def update_kandang(
    kandang_id: uuid.UUID,
    request: Request,
    kandang_data: KandangUpdate,
    current_user: User = Depends(require_roles(UserRole.PETERNAK)),
    db: AsyncSession = Depends(get_db),
):
    kandang_service = KandangService(db)

    kandang = await kandang_service.get_by_id(kandang_id)
    if not kandang:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kandang tidak ditemukan",
        )

    updated = await kandang_service.update(kandang, kandang_data)

    request_info = await get_request_info(request)
    activity_service = ActivityLogService(db)
    await activity_service.log_action(
        user_id=current_user.id,
        action="update_kandang",
        resource="kandang",
        resource_id=kandang_id,
        request_info=request_info,
        details={"updated_fields": list(kandang_data.model_dump(exclude_unset=True).keys())},
    )

    response = KandangResponse.model_validate(updated)

    return success_response(
        data=response,
        message="Kandang berhasil diupdate",
    )
