import uuid
from typing import Optional, List

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.kandang import Kandang
from app.models.sensor_data import SensorData
from app.models.user import User
from app.schemas.kandang import KandangCreate, KandangUpdate, LatestSensorSnapshot


class KandangService:
    """Service for kandang (cage/barn) operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_id(self, kandang_id: uuid.UUID) -> Optional[Kandang]:
        """Get kandang by ID."""
        query = select(Kandang).options(
            joinedload(Kandang.pemilik)
        ).where(Kandang.id == kandang_id)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_kode(self, kode: str) -> Optional[Kandang]:
        """Get kandang by kode."""
        query = select(Kandang).where(Kandang.kode == kode)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_list(
        self,
        page: int = 1,
        per_page: int = 10,
        pemilik_id: Optional[uuid.UUID] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> tuple[List[Kandang], int]:
        """Get paginated list of kandangs with filters."""
        query = select(Kandang).options(joinedload(Kandang.pemilik))
        count_query = select(func.count(Kandang.id))
        
        # Apply filters
        if pemilik_id:
            query = query.where(Kandang.pemilik_id == pemilik_id)
            count_query = count_query.where(Kandang.pemilik_id == pemilik_id)
        
        if is_active is not None:
            query = query.where(Kandang.is_active == is_active)
            count_query = count_query.where(Kandang.is_active == is_active)
        
        if search:
            search_filter = Kandang.nama.ilike(f"%{search}%") | Kandang.kode.ilike(f"%{search}%")
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()
        
        # Apply pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page).order_by(Kandang.created_at.desc())
        
        result = await self.db.execute(query)
        kandangs = result.scalars().unique().all()
        
        return list(kandangs), total
    
    async def create(self, kandang_data: KandangCreate) -> Kandang:
        """Create a new kandang."""
        kandang = Kandang(
            nama=kandang_data.nama,
            kode=kandang_data.kode,
            lokasi=kandang_data.lokasi,
            kapasitas=kandang_data.kapasitas,
            deskripsi=kandang_data.deskripsi,
            pemilik_id=kandang_data.pemilik_id,
        )
        
        self.db.add(kandang)
        await self.db.flush()
        await self.db.refresh(kandang)
        
        return kandang
    
    async def update(self, kandang: Kandang, kandang_data: KandangUpdate) -> Kandang:
        """Update an existing kandang."""
        update_data = kandang_data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(kandang, field, value)
        
        await self.db.flush()
        await self.db.refresh(kandang)
        
        return kandang
    
    async def delete(self, kandang: Kandang) -> bool:
        """Hard delete a kandang."""
        await self.db.delete(kandang)
        await self.db.flush()
        return True
    
    async def get_latest_sensor(self, kandang_id: uuid.UUID) -> Optional[LatestSensorSnapshot]:
        """Ambil data sensor terbaru untuk satu kandang."""
        result = await self.db.execute(
            select(SensorData)
            .where(SensorData.kandang_id == kandang_id)
            .order_by(desc(SensorData.timestamp))
            .limit(1)
        )
        sensor = result.scalar_one_or_none()
        if not sensor:
            return None
        return LatestSensorSnapshot.model_validate(sensor)

    async def deactivate(self, kandang: Kandang) -> Kandang:
        """Soft delete (deactivate) a kandang."""
        kandang.is_active = False
        await self.db.flush()
        await self.db.refresh(kandang)
        return kandang
