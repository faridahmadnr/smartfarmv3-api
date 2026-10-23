import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.models.kandang import Kandang
from app.schemas.kandang import KandangCreate, KandangUpdate, KandangResponse
from app.schemas.base import BaseResponse, PaginatedResponse, success_response, paginated_response
from app.services.kandang_service import KandangService
from app.services.activity_log_service import ActivityLogService
from app.api.deps import get_current_user, require_roles, get_request_info

router = APIRouter()


@router.get(
    "/me",
    response_model=BaseResponse[KandangResponse],
    summary="Get Kandang Default",
    description="Get detail kandang aktif pertama (kompatibilitas legacy)",
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


@router.get(
    "",
    response_model=PaginatedResponse[KandangResponse],
    summary="List Kandang",
    description="Ambil daftar semua kandang milik pengguna",
)
async def list_kandangs(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kandang_service = KandangService(db)
    skip = (page - 1) * per_page
    kandangs, total = await kandang_service.get_all_by_user(
        user_id=current_user.id,
        role=current_user.role,
        skip=skip,
        limit=per_page,
    )

    items = []
    for k in kandangs:
        resp = KandangResponse.model_validate(k)
        if k.pemilik:
            resp.pemilik_name = k.pemilik.full_name
        resp.latest_sensor = await kandang_service.get_latest_sensor(k.id)
        items.append(resp)

    return paginated_response(
        data=items,
        total=total,
        page=page,
        per_page=per_page,
        message="Daftar kandang berhasil diambil",
    )


@router.post(
    "",
    response_model=BaseResponse[KandangResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create Kandang",
    description="Tambah kandang baru (Pemilik atau Admin)",
)
async def create_kandang(
    kandang_data: KandangCreate,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PEMILIK)),
    db: AsyncSession = Depends(get_db),
):
    kandang_service = KandangService(db)

    # Jika yang login Pemilik atau pemilik_id tidak diisi, otomatis set pemilik_id ke akunnya sendiri
    if current_user.role == UserRole.PEMILIK or not kandang_data.pemilik_id:
        kandang_data.pemilik_id = current_user.id

    # Cek apakah kode kandang sudah dipakai
    existing = await kandang_service.get_by_kode(kandang_data.kode)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Kandang dengan kode '{kandang_data.kode}' sudah ada",
        )

    new_kandang = await kandang_service.create(kandang_data)

    request_info = await get_request_info(request)
    activity_service = ActivityLogService(db)
    await activity_service.log_action(
        user_id=current_user.id,
        action="create_kandang",
        resource="kandang",
        resource_id=new_kandang.id,
        request_info=request_info,
    )

    response = KandangResponse.model_validate(new_kandang)
    return success_response(data=response, message="Kandang berhasil dibuat")


@router.get(
    "/{kandang_id}",
    response_model=BaseResponse[KandangResponse],
    summary="Get Kandang by ID",
    description="Ambil detail 1 kandang berdasarkan ID",
)
async def get_kandang_by_id(
    kandang_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kandang_service = KandangService(db)
    kandang = await kandang_service.get_by_id(kandang_id)
    if not kandang:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kandang tidak ditemukan",
        )

    # Validasi akses jika bukan admin
    if current_user.role == UserRole.PEMILIK and kandang.pemilik_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses ditolak: bukan pemilik kandang ini")

    response = KandangResponse.model_validate(kandang)
    if kandang.pemilik:
        response.pemilik_name = kandang.pemilik.full_name
    response.latest_sensor = await kandang_service.get_latest_sensor(kandang.id)
    return success_response(data=response, message="Data kandang berhasil diambil")


@router.put(
    "/{kandang_id}",
    response_model=BaseResponse[KandangResponse],
    summary="Update Kandang",
    description="Update data kandang (Admin, Pemilik, atau Peternak)",
)
async def update_kandang(
    kandang_id: uuid.UUID,
    request: Request,
    kandang_data: KandangUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PEMILIK, UserRole.PETERNAK)),
    db: AsyncSession = Depends(get_db),
):
    kandang_service = KandangService(db)

    kandang = await kandang_service.get_by_id(kandang_id)
    if not kandang:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kandang tidak ditemukan",
        )

    # Validasi kepemilikan
    if current_user.role == UserRole.PEMILIK and kandang.pemilik_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses ditolak: bukan pemilik kandang ini")

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


@router.delete(
    "/{kandang_id}",
    response_model=BaseResponse[dict],
    summary="Delete / Deactivate Kandang",
    description="Nonaktifkan kandang (Soft delete - Pemilik atau Admin)",
)
async def delete_kandang(
    kandang_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.PEMILIK)),
    db: AsyncSession = Depends(get_db),
):
    kandang_service = KandangService(db)

    kandang = await kandang_service.get_by_id(kandang_id)
    if not kandang:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kandang tidak ditemukan",
        )

    if current_user.role == UserRole.PEMILIK and kandang.pemilik_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Akses ditolak: bukan pemilik kandang ini")

    await kandang_service.deactivate(kandang)

    request_info = await get_request_info(request)
    activity_service = ActivityLogService(db)
    await activity_service.log_action(
        user_id=current_user.id,
        action="delete_kandang",
        resource="kandang",
        resource_id=kandang_id,
        request_info=request_info,
    )

    return success_response(
        data={"id": str(kandang_id), "is_active": False},
        message="Kandang berhasil dinonaktifkan",
    )
