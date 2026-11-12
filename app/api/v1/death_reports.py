import io
import csv
from fastapi.responses import StreamingResponse
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.kandang import Kandang
from app.schemas.base import BaseResponse, success_response
from app.schemas.death_report import DeathReportCreate, DeathReportResponse, DeathReportListResponse
from app.services.death_report_service import DeathReportService
from app.api.deps import get_current_user, get_single_kandang


class DeathReportUpdate(BaseModel):
    count: Optional[int] = Field(default=None, ge=1)
    notes: Optional[str] = Field(default=None, max_length=500)
    timestamp: Optional[datetime] = None

router = APIRouter()


@router.post(
    "",
    response_model=BaseResponse[DeathReportResponse],
    summary="Laporkan Kematian",
    description="Catat kejadian kematian ayam",
)
async def report_death(
    data: DeathReportCreate,
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    service = DeathReportService(db)
    report = await service.create(data, kandang_id=kandang.id, reported_by=current_user.id)
    return success_response(
        data=DeathReportResponse.model_validate(report),
        message=f"Kematian {report.count} ekor berhasil dicatat",
    )


@router.get(
    "",
    response_model=BaseResponse[DeathReportListResponse],
    summary="Riwayat Laporan Kematian",
)
async def list_death_reports(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    service = DeathReportService(db)
    items, total = await service.get_list(kandang.id, page, per_page)
    return success_response(
        data=DeathReportListResponse(
            items=[DeathReportResponse.model_validate(r) for r in items],
            total=total,
            page=page,
            per_page=per_page,
        ),
        message="Riwayat laporan kematian berhasil diambil",
    )



@router.get(
    "/export/csv",
    summary="Ekspor Laporan Kematian ke CSV",
    description="Ekspor riwayat data laporan kematian ayam ke file CSV.",
)
async def export_death_reports_csv(
    start_time: Optional[datetime] = Query(None, description="Filter awal"),
    end_time: Optional[datetime] = Query(None, description="Filter akhir"),
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    service = DeathReportService(db)
    items = await service.get_all_for_export(kandang.id, start_time, end_time)

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=",")
    writer.writerow([
        "Waktu Kejadian",
        "Jumlah Kematian (ekor)",
        "Catatan / Penyebab",
    ])

    for item in items:
        writer.writerow([
            item.timestamp.strftime("%Y-%m-%d %H:%M:%S") if item.timestamp else "",
            item.count,
            item.notes or "",
        ])

    k_name = kandang.kode or kandang.nama or "kandang"
    s_label = start_time.strftime("%Y%m%d_%H%M") if start_time else "awal"
    e_label = end_time.strftime("%Y%m%d_%H%M") if end_time else "akhir"
    filename = f"kematian_{k_name}_{s_label}_{e_label}.csv".replace(" ", "_")

    try:
        from app.services.activity_log_service import ActivityLogService
        from app.models.activity_log import Platform
        activity_service = ActivityLogService(db)
        await activity_service.create(
            user_id=current_user.id,
            action="EXPORT_CSV",
            resource="death_reports",
            resource_id=kandang.id,
            details={"kandang_nama": kandang.nama, "total_rows": len(items)},
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
    "/{report_id}",
    response_model=BaseResponse[DeathReportResponse],
    summary="Edit Laporan Kematian",
)
async def update_death_report(
    report_id: uuid.UUID,
    data: DeathReportUpdate,
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    service = DeathReportService(db)
    report = await service.update(report_id, kandang.id, data.count, data.notes, data.timestamp)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Laporan tidak ditemukan")
    return success_response(data=DeathReportResponse.model_validate(report), message="Laporan berhasil diperbarui")


@router.delete(
    "/{report_id}",
    summary="Hapus Laporan Kematian",
)
async def delete_death_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    service = DeathReportService(db)
    deleted = await service.delete(report_id, kandang.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Laporan tidak ditemukan")
    return success_response(data={"id": str(report_id)}, message="Laporan berhasil dihapus")


@router.get(
    "/today-total",
    response_model=BaseResponse[dict],
    summary="Total Kematian Hari Ini",
)
async def get_today_total(
    current_user: User = Depends(get_current_user),
    kandang: Kandang = Depends(get_single_kandang),
    db: AsyncSession = Depends(get_db),
):
    service = DeathReportService(db)
    total = await service.get_total_today(kandang.id)
    return success_response(data={"total": total}, message="Total kematian hari ini")
