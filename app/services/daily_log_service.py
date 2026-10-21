import uuid
from datetime import datetime, date
from typing import Optional, List

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_log import DailyLog
from app.schemas.daily_log import DailyLogCreate



class DailyLogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_or_update(
        self,
        data: DailyLogCreate,
        kandang_id: uuid.UUID,
        recorded_by: Optional[uuid.UUID] = None,
    ) -> DailyLog:
        log_date = data.date or date.today()

        existing = await self.get_by_date(kandang_id, log_date)
        if existing:
            update_data = data.model_dump(exclude_unset=True, exclude={"date"})
            for field, value in update_data.items():
                if value is not None:
                    setattr(existing, field, value)
            existing.recorded_by = recorded_by
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        log = DailyLog(
            kandang_id=kandang_id,
            date=log_date,
            pakan=data.pakan,
            minum=data.minum,
            populasi=data.populasi,
            bobot=data.bobot,
            notes=data.notes,
            recorded_by=recorded_by,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def get_by_date(self, kandang_id: uuid.UUID, log_date: date) -> Optional[DailyLog]:
        result = await self.db.execute(
            select(DailyLog).where(
                DailyLog.kandang_id == kandang_id,
                DailyLog.date == log_date,
            )
        )
        return result.scalar_one_or_none()

    async def get_today(self, kandang_id: uuid.UUID) -> Optional[DailyLog]:
        return await self.get_by_date(kandang_id, date.today())

    async def get_by_id(self, log_id: uuid.UUID, kandang_id: uuid.UUID) -> Optional[DailyLog]:
        result = await self.db.execute(
            select(DailyLog).where(DailyLog.id == log_id, DailyLog.kandang_id == kandang_id)
        )
        return result.scalar_one_or_none()

    async def update(self, log_id: uuid.UUID, kandang_id: uuid.UUID, data: "DailyLogCreate") -> Optional[DailyLog]:
        log = await self.get_by_id(log_id, kandang_id)
        if not log:
            return None
        update_fields = data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(log, field, value)
        await self.db.commit()
        await self.db.refresh(log)
        return log

    async def delete(self, log_id: uuid.UUID, kandang_id: uuid.UUID) -> bool:
        log = await self.get_by_id(log_id, kandang_id)
        if not log:
            return False
        await self.db.delete(log)
        await self.db.commit()
        return True

    async def get_list(
        self,
        kandang_id: uuid.UUID,
        page: int = 1,
        per_page: int = 30,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> tuple[List[DailyLog], int]:
        filters = [DailyLog.kandang_id == kandang_id]
        if start_date:
            filters.append(DailyLog.date >= start_date)
        if end_date:
            filters.append(DailyLog.date <= end_date)

        count_result = await self.db.execute(
            select(func.count(DailyLog.id)).where(*filters)
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            select(DailyLog)
            .where(*filters)
            .order_by(desc(DailyLog.date))
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        return list(result.scalars().all()), total
