import uuid
from typing import Optional, List

from fastapi import HTTPException, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.kandang import Kandang
from app.models.sensor_data import SensorData
from app.models.user import User, UserRole
from app.schemas.kandang import KandangCreate, KandangUpdate, LatestSensorSnapshot


def check_kandang_access(kandang: Kandang, user: User) -> bool:
    """
    Validasi hak akses ke kandang:
    - ADMIN: selalu boleh mengakses semua kandang.
    - PEMILIK: hanya boleh mengakses kandang miliknya (kandang.pemilik_id == user.id).
    - PETERNAK: hanya boleh mengakses kandang milik pemilik yang menaunginya
      (user.pemilik_id is not None dan kandang.pemilik_id == user.pemilik_id).
    - Role lain atau peternak tanpa pemilik_id: ditolak (False).
    """
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.PEMILIK:
        return kandang.pemilik_id == user.id
    if user.role == UserRole.PETERNAK:
        return user.pemilik_id is not None and kandang.pemilik_id == user.pemilik_id
    return False


def ensure_kandang_access(kandang: Kandang, user: User) -> None:
    """
    Raise HTTP 403 Forbidden jika user tidak memiliki hak akses ke kandang.
    Dapat dipakai ulang di router kandang maupun dependencies (mis. get_single_kandang).
    """
    if not check_kandang_access(kandang, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Akses ditolak: Anda tidak memiliki akses ke kandang ini",
        )


class KandangService:
    """Service for kandang (cage/barn) operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db

    def check_access(self, kandang: Kandang, user: User) -> bool:
        """Instance helper untuk check_kandang_access."""
        return check_kandang_access(kandang, user)

    def ensure_access(self, kandang: Kandang, user: User) -> None:
        """Instance helper untuk ensure_kandang_access."""
        ensure_kandang_access(kandang, user)

    async def get_my_kandang(self, user: User) -> Optional[Kandang]:
        """
        Ambil kandang aktif pertama sesuai scope role user:
        - ADMIN: kandang aktif pertama secara global.
        - PEMILIK: kandang aktif pertama milik user.
        - PETERNAK: kandang aktif pertama milik pemilik yang menaunginya.
        - Peternak tanpa pemilik_id / lainnya: None.
        """
        query = (
            select(Kandang)
            .options(joinedload(Kandang.pemilik))
            .where(Kandang.is_active == True)
        )
        if user.role == UserRole.PEMILIK:
            query = query.where(Kandang.pemilik_id == user.id)
        elif user.role == UserRole.PETERNAK:
            if not user.pemilik_id:
                return None
            query = query.where(Kandang.pemilik_id == user.pemilik_id)
        elif user.role == UserRole.ADMIN:
            pass
        else:
            return None

        query = query.order_by(Kandang.created_at.asc()).limit(1)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
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
        luas_val = kandang_data.luas
        if luas_val is None and kandang_data.panjang is not None and kandang_data.lebar is not None:
            luas_val = round(kandang_data.panjang * kandang_data.lebar, 2)

        kandang = Kandang(
            nama=kandang_data.nama,
            kode=kandang_data.kode,
            lokasi=kandang_data.lokasi,
            kapasitas=kandang_data.kapasitas,
            panjang=kandang_data.panjang,
            lebar=kandang_data.lebar,
            luas=luas_val,
            tipe_kandang=kandang_data.tipe_kandang or "Closed House",
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

        # Auto-recalculate luas jika panjang atau lebar diupdate dan luas tidak di-override manual
        if "luas" not in update_data and (kandang.panjang is not None and kandang.lebar is not None):
            kandang.luas = round(kandang.panjang * kandang.lebar, 2)
        
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
    
    async def get_all_by_user(
        self, user_id: uuid.UUID, role: str, skip: int = 0, limit: int = 100
    ) -> tuple[list[Kandang], int]:
        """
        Ambil semua kandang:
        - Jika ADMIN: ambil seluruh kandang yang ada di sistem.
        - Jika PEMILIK: ambil kandang miliknya sendiri.
        - Jika PETERNAK: ambil kandang milik pemilik yang menaunginya.
        """
        query = select(Kandang).options(joinedload(Kandang.pemilik)).where(Kandang.is_active == True)
        count_query = select(func.count(Kandang.id)).where(Kandang.is_active == True)

        if role == UserRole.PEMILIK:
            query = query.where(Kandang.pemilik_id == user_id)
            count_query = count_query.where(Kandang.pemilik_id == user_id)
        elif role == UserRole.PETERNAK:
            user_res = await self.db.execute(select(User).where(User.id == user_id))
            user = user_res.scalar_one_or_none()
            owner_id = user.pemilik_id if user else None
            if not owner_id:
                return [], 0
            query = query.where(Kandang.pemilik_id == owner_id)
            count_query = count_query.where(Kandang.pemilik_id == owner_id)

        total = (await self.db.execute(count_query)).scalar_one()

        # Ambil data dengan pagination
        query = query.order_by(Kandang.nama).offset(skip).limit(limit)
        res = await self.db.execute(query)
        kandangs = list(res.scalars().unique().all())
        return kandangs, total
