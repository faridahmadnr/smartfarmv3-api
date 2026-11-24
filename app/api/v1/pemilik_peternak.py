import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import require_pemilik
from app.models.user import User
from app.schemas.base import BaseResponse, PaginatedResponse, success_response, paginated_response
from app.schemas.user import PeternakCreate, PeternakUpdate, UserResponse
from app.services.user_service import UserService

router = APIRouter()


@router.get(
    "",
    response_model=PaginatedResponse[UserResponse],
    summary="List Peternak Milik Pemilik",
    description="Mengambil daftar peternak yang berada di bawah naungan pemilik yang sedang login.",
)
async def list_my_peternaks(
    page: int = Query(default=1, ge=1, description="Nomor halaman"),
    per_page: int = Query(default=10, ge=1, le=100, description="Jumlah item per halaman"),
    is_active: Optional[bool] = Query(default=None, description="Filter status aktif"),
    search: Optional[str] = Query(default=None, description="Pencarian nama/username/email"),
    current_user: User = Depends(require_pemilik()),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    peternaks, total = await service.get_peternaks_paginated_by_pemilik(
        pemilik_id=current_user.id,
        page=page,
        per_page=per_page,
        is_active=is_active,
        search=search,
    )
    items = [UserResponse.model_validate(p) for p in peternaks]
    return paginated_response(
        data=items,
        total=total,
        page=page,
        per_page=per_page,
        message="Daftar peternak berhasil diambil",
    )


@router.post(
    "",
    response_model=BaseResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Tambah Peternak Baru",
    description="Pemilik menambahkan akun peternak baru yang otomatis dinaungi oleh akunnya.",
)
async def create_my_peternak(
    data: PeternakCreate,
    current_user: User = Depends(require_pemilik()),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    new_peternak = await service.create_peternak(pemilik_id=current_user.id, data=data)
    await db.commit()
    return success_response(
        data=UserResponse.model_validate(new_peternak),
        message="Peternak berhasil ditambahkan",
    )


@router.get(
    "/{peternak_id}",
    response_model=BaseResponse[UserResponse],
    summary="Detail Peternak",
    description="Melihat profil peternak milik sendiri.",
)
async def get_my_peternak_detail(
    peternak_id: uuid.UUID,
    current_user: User = Depends(require_pemilik()),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    peternak = await service.get_peternak_by_id_and_pemilik(
        peternak_id=peternak_id, pemilik_id=current_user.id
    )
    if not peternak:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peternak tidak ditemukan",
        )
    return success_response(
        data=UserResponse.model_validate(peternak),
        message="Data peternak berhasil diambil",
    )


@router.put(
    "/{peternak_id}",
    response_model=BaseResponse[UserResponse],
    summary="Update Peternak",
    description="Memperbarui data peternak milik sendiri.",
)
async def update_my_peternak(
    peternak_id: uuid.UUID,
    data: PeternakUpdate,
    current_user: User = Depends(require_pemilik()),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    peternak = await service.get_peternak_by_id_and_pemilik(
        peternak_id=peternak_id, pemilik_id=current_user.id
    )
    if not peternak:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peternak tidak ditemukan",
        )

    updated_peternak = await service.update_peternak(peternak=peternak, data=data)
    await db.commit()
    return success_response(
        data=UserResponse.model_validate(updated_peternak),
        message="Data peternak berhasil diperbarui",
    )


@router.delete(
    "/{peternak_id}",
    response_model=BaseResponse[dict],
    summary="Nonaktifkan Peternak (Soft Delete)",
    description="Menonaktifkan akun peternak dan langsung mencabut token sesi aktifnya.",
)
async def delete_my_peternak(
    peternak_id: uuid.UUID,
    current_user: User = Depends(require_pemilik()),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    peternak = await service.get_peternak_by_id_and_pemilik(
        peternak_id=peternak_id, pemilik_id=current_user.id
    )
    if not peternak:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Peternak tidak ditemukan",
        )

    # Idempotent: jika sudah nonaktif, tetap deactive (cabut token jika ada) dan return sukses
    await service.deactivate_peternak(peternak)
    await db.commit()
    return success_response(
        data={"id": str(peternak_id), "is_active": False},
        message="Peternak berhasil dinonaktifkan",
    )
