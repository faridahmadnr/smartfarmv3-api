import uuid
import datetime
import io
import csv
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.kandang import Kandang
from app.schemas.base import BaseResponse, success_response
from app.schemas.daily_log import DailyLogCreate, DailyLogResponse, DailyLogListResponse
from app.services.daily_log_service import DailyLogService
from app.api.deps import get_current_user, get_single_kandang

router = APIRouter()


@router.post(
    "",
    response_model=BaseResponse[DailyLogResponse],
    summary="Input Log Harian",
    description="Catat pakan, minum, populasi, bobot harian. Upsert berdasarkan tanggal.",
)
async def create_daily_log(
    data: DailyLogCreate,
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    service = DailyLogService(db)
    log = await service.create_or_update(data, kandang_id=kandang.id, recorded_by=current_user.id)
    return success_response(
        data=DailyLogResponse.model_validate(log),
        message="Log harian berhasil disimpan",
    )


@router.get(
    "/export/csv",
    summary="Ekspor Log Harian ke CSV",
    description="Ekspor riwayat data operasional log harian dan kematian ke file CSV (UTF-8 BOM untuk Microsoft Excel).",
)
async def export_daily_logs_csv(
    start_date: Optional[datetime.date] = Query(None, description="Filter dari tanggal (YYYY-MM-DD)"),
    end_date: Optional[datetime.date] = Query(None, description="Filter hingga tanggal (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    service = DailyLogService(db)
    logs, death_map = await service.get_all_for_export(kandang.id, start_date, end_date)

    output = io.StringIO()
    output.write("\ufeff")  # UTF-8 BOM
    writer = csv.writer(output, delimiter=",")
    writer.writerow([
        "Tanggal",
        "Pakan (kg)",
        "Minum (L)",
        "Populasi (ekor)",
        "Bobot Rata-rata (g)",
        "Kematian (ekor)",
        "Catatan",
    ])

    for item in logs:
        writer.writerow([
            item.date.strftime("%Y-%m-%d") if item.date else "",
            item.pakan if item.pakan is not None else "",
            item.minum if item.minum is not None else "",
            item.populasi if item.populasi is not None else "",
            item.bobot if item.bobot is not None else "",
            death_map.get(item.date, 0),
            item.notes or "",
        ])

    k_name = kandang.kode or kandang.nama or "kandang"
    s_label = start_date.strftime("%Y%m%d") if start_date else "awal"
    e_label = end_date.strftime("%Y%m%d") if end_date else "akhir"
    filename = f"log_harian_{k_name}_{s_label}_{e_label}.csv".replace(" ", "_")

    # Audit activity log
    try:
        from app.services.activity_log_service import ActivityLogService
        from app.models.activity_log import Platform
        activity_service = ActivityLogService(db)
        await activity_service.create(
            user_id=current_user.id,
            action="EXPORT_CSV",
            resource="daily_logs",
            resource_id=kandang.id,
            details={"kandang_nama": kandang.nama, "total_rows": len(logs)},
            platform=Platform.WEB,
        )
        await db.commit()
    except Exception:
        pass

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.put(
    "/{log_id}",
    response_model=BaseResponse[DailyLogResponse],
    summary="Edit Log Harian",
)
async def update_daily_log(
    log_id: uuid.UUID,
    data: DailyLogCreate,
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    service = DailyLogService(db)
    log = await service.update(log_id, kandang.id, data)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log tidak ditemukan")
    return success_response(data=DailyLogResponse.model_validate(log), message="Log harian berhasil diperbarui")


@router.delete(
    "/{log_id}",
    summary="Hapus Log Harian",
)
async def delete_daily_log(
    log_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    service = DailyLogService(db)
    deleted = await service.delete(log_id, kandang.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log tidak ditemukan")
    return success_response(data={"id": str(log_id)}, message="Log harian berhasil dihapus")


@router.get(
    "/today",
    response_model=BaseResponse[DailyLogResponse],
    summary="Log Harian Hari Ini",
)
async def get_today_log(
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    service = DailyLogService(db)
    log = await service.get_today(kandang.id)
    if not log:
        return success_response(data=None, message="Belum ada log hari ini")
    return success_response(
        data=DailyLogResponse.model_validate(log),
        message="Log harian hari ini berhasil diambil",
    )


@router.get(
    "",
    response_model=BaseResponse[DailyLogListResponse],
    summary="Riwayat Log Harian",
)
async def list_daily_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
    start_date: datetime.date = Query(None, description="Filter dari tanggal (YYYY-MM-DD)"),
    end_date: datetime.date = Query(None, description="Filter hingga tanggal (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    service = DailyLogService(db)
    items, total = await service.get_list(kandang.id, page, per_page, start_date, end_date)
    return success_response(
        data=DailyLogListResponse(
            items=[DailyLogResponse.model_validate(item) for item in items],
            total=total,
            page=page,
            per_page=per_page,
        ),
        message="Riwayat log harian berhasil diambil",
    )
