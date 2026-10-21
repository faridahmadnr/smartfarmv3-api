"""
Sensor Data Service - Business logic for IoT sensor data management
"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sensor_data import SensorData
from app.models.kandang import Kandang
from app.schemas.sensor_data import (
    SensorDataCreate, 
    SensorDataManualUpdate,
    SensorDataStats,
)


class SensorDataService:
    """Service class for sensor data operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self,
        data: SensorDataCreate,
        kandang_id: uuid.UUID,
        recorded_by: Optional[uuid.UUID] = None
    ) -> SensorData:
        sensor_data = SensorData(
            kandang_id=kandang_id,
            timestamp=data.timestamp,
            hari_ke=data.hari_ke,
            suhu=data.suhu,
            kelembaban=data.kelembaban,
            amoniak=data.amoniak,
            pakan=data.pakan,
            minum=data.minum,
            bobot=data.bobot,
            populasi=data.populasi,
            death=data.death,
            recorded_by=recorded_by,
        )
        self.db.add(sensor_data)
        await self.db.commit()
        await self.db.refresh(sensor_data)
        return sensor_data
    
    async def get_by_id(self, sensor_data_id: uuid.UUID) -> Optional[SensorData]:
        """Get sensor data by ID."""
        result = await self.db.execute(
            select(SensorData).where(SensorData.id == sensor_data_id)
        )
        return result.scalar_one_or_none()
    
    async def update_manual_fields(
        self,
        sensor_data_id: uuid.UUID,
        data: SensorDataManualUpdate,
        updated_by: uuid.UUID
    ) -> Optional[SensorData]:
        """Update manually-input fields of a sensor data record."""
        sensor_data = await self.get_by_id(sensor_data_id)
        if not sensor_data:
            return None
        
        # Only update provided fields
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(sensor_data, field, value)
        
        sensor_data.recorded_by = updated_by
        await self.db.commit()
        await self.db.refresh(sensor_data)
        return sensor_data
    
    async def get_by_kandang(
        self,
        kandang_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> tuple[List[SensorData], int]:
        """Get sensor data for a kandang with pagination."""
        query = select(SensorData).where(SensorData.kandang_id == kandang_id)
        
        if start_time:
            query = query.where(SensorData.timestamp >= start_time)
        if end_time:
            query = query.where(SensorData.timestamp <= end_time)
        
        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()
        
        # Get paginated results
        query = query.order_by(desc(SensorData.timestamp))
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        items = list(result.scalars().all())
        
        return items, total
    
    async def get_latest(
        self,
        kandang_id: uuid.UUID,
        limit: int = 4
    ) -> List[SensorData]:
        """Get latest N sensor data records for a kandang."""
        result = await self.db.execute(
            select(SensorData)
            .where(SensorData.kandang_id == kandang_id)
            .order_by(desc(SensorData.timestamp))
            .limit(limit)
        )
        # Return in chronological order (oldest first)
        return list(reversed(result.scalars().all()))
    
    async def get_stats(
        self,
        kandang_id: uuid.UUID,
        hours: int = 24
    ) -> Optional[SensorDataStats]:
        """Get statistical summary for a kandang over the specified hours."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        result = await self.db.execute(
            select(
                func.count(SensorData.id).label('total_readings'),
                func.avg(SensorData.suhu).label('avg_suhu'),
                func.avg(SensorData.kelembaban).label('avg_kelembaban'),
                func.avg(SensorData.amoniak).label('avg_amoniak'),
                func.sum(SensorData.death).label('total_deaths'),
            )
            .where(
                and_(
                    SensorData.kandang_id == kandang_id,
                    SensorData.timestamp >= start_time,
                    SensorData.timestamp <= end_time,
                )
            )
        )
        row = result.one()
        
        if row.total_readings == 0:
            return None
        
        # Get latest population
        latest = await self.db.execute(
            select(SensorData.populasi)
            .where(
                and_(
                    SensorData.kandang_id == kandang_id,
                    SensorData.populasi.isnot(None)
                )
            )
            .order_by(desc(SensorData.timestamp))
            .limit(1)
        )
        latest_pop = latest.scalar_one_or_none()
        
        return SensorDataStats(
            kandang_id=kandang_id,
            period_start=start_time,
            period_end=end_time,
            total_readings=row.total_readings,
            avg_suhu=float(row.avg_suhu or 0),
            avg_kelembaban=float(row.avg_kelembaban or 0),
            avg_amoniak=float(row.avg_amoniak or 0),
            total_deaths=int(row.total_deaths or 0),
            latest_populasi=latest_pop,
        )
    
    async def get_latest_at_interval(
        self,
        kandang_id: uuid.UUID,
        n_points: int = 4,
        interval_minutes: int = 30,
    ) -> List[SensorData]:
        """
        Ambil N data point dengan jarak ~interval_minutes antar titik.
        Digunakan untuk forecasting ML yang dilatih dengan data 30-menit interval.

        Cara kerja: dari data dalam lookback window, ambil 1 data per bucket interval.
        """
        lookback = timedelta(minutes=n_points * interval_minutes)
        start_time = datetime.utcnow() - lookback

        result = await self.db.execute(
            select(SensorData)
            .where(
                and_(
                    SensorData.kandang_id == kandang_id,
                    SensorData.timestamp >= start_time,
                )
            )
            .order_by(SensorData.timestamp)
        )
        all_data = list(result.scalars().all())

        if not all_data:
            return []

        # Pilih 1 data per window interval_minutes (ambil yang pertama di tiap bucket)
        sampled: List[SensorData] = []
        interval_delta = timedelta(minutes=interval_minutes)
        last_picked: Optional[datetime] = None

        for reading in all_data:
            ts = reading.timestamp.replace(tzinfo=None) if reading.timestamp.tzinfo else reading.timestamp
            if last_picked is None or (ts - last_picked) >= interval_delta:
                sampled.append(reading)
                last_picked = ts

        return sampled[-n_points:]

    async def get_hari_ke(self, kandang_id: uuid.UUID, tanggal_mulai_siklus=None) -> int:
        """Hitung hari ke- berdasarkan tanggal_mulai_siklus kandang.
        Fallback ke data sensor pertama jika tanggal_mulai_siklus belum di-set."""
        if tanggal_mulai_siklus is not None:
            start = tanggal_mulai_siklus.replace(tzinfo=None)
        else:
            result = await self.db.execute(
                select(func.min(SensorData.timestamp))
                .where(SensorData.kandang_id == kandang_id)
            )
            start = result.scalar_one_or_none()
            if not start:
                return 1
            start = start.replace(tzinfo=None)

        delta = datetime.utcnow() - start
        return max(1, delta.days + 1)

    async def delete(self, sensor_data_id: uuid.UUID) -> bool:
        """Delete a sensor data record."""
        sensor_data = await self.get_by_id(sensor_data_id)
        if not sensor_data:
            return False
        
        await self.db.delete(sensor_data)
        await self.db.commit()
        return True
    
    async def get_for_forecasting(
        self,
        kandang_id: uuid.UUID,
        n_points: int = 4
    ) -> List[Dict[str, Any]]:
        """Get sensor data formatted for forecasting model input."""
        data = await self.get_latest(kandang_id, n_points)
        
        return [
            {
                'temp': d.suhu,
                'hum': d.kelembaban,
                'ammo': d.amoniak,
                'Death': d.death
            }
            for d in data
        ]
