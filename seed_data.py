"""
Script to seed initial data: pemilik, peternak, dan kandang.
Run after create_admin.py.

Usage:
    python seed_data.py
"""
import asyncio
import sys

sys.path.insert(0, ".")

from app.database import async_session_maker, create_tables
from app.models.user import User, UserRole
from app.models.kandang import Kandang
from app.core.security import get_password_hash
from sqlalchemy import select


async def seed():
    await create_tables()

    async with async_session_maker() as session:
        # --- Cek admin ---
        admin = (await session.execute(
            select(User).where(User.username == "admin")
        )).scalar_one_or_none()

        if not admin:
            print("❌ Admin belum dibuat. Jalankan create_admin.py dulu!")
            return

        # --- Buat Pemilik ---
        existing_pemilik = (await session.execute(
            select(User).where(User.username == "pemilik")
        )).scalar_one_or_none()

        if existing_pemilik:
            print("⚠️  Pemilik sudah ada, skip.")
            pemilik = existing_pemilik
        else:
            pemilik = User(
                email="pemilik@broilabs.com",
                username="pemilik",
                hashed_password=get_password_hash("pemilik123"),
                full_name="Pemilik Kandang",
                phone="08123456789",
                role=UserRole.PEMILIK,
                created_by_id=admin.id,
            )
            session.add(pemilik)
            await session.flush()
            print("✅ Pemilik dibuat: pemilik / pemilik123")

        # --- Buat Peternak ---
        existing_peternak = (await session.execute(
            select(User).where(User.username == "peternak")
        )).scalar_one_or_none()

        if existing_peternak:
            print("⚠️  Peternak sudah ada, skip.")
        else:
            peternak = User(
                email="peternak@broilabs.com",
                username="peternak",
                hashed_password=get_password_hash("peternak123"),
                full_name="Peternak Kandang",
                phone="08987654321",
                role=UserRole.PETERNAK,
                pemilik_id=pemilik.id,
                created_by_id=admin.id,
            )
            session.add(peternak)
            print("✅ Peternak dibuat: peternak / peternak123")

        # --- Buat Kandang ---
        existing_kandang = (await session.execute(
            select(Kandang).where(Kandang.kode == "KDG-001")
        )).scalar_one_or_none()

        if existing_kandang:
            print("⚠️  Kandang sudah ada, skip.")
        else:
            kandang = Kandang(
                nama="Kandang Utama",
                kode="KDG-001",
                lokasi="Lokasi Kandang",
                kapasitas=1000,
                deskripsi="Kandang broiler utama",
                pemilik_id=pemilik.id,
            )
            session.add(kandang)
            print("✅ Kandang dibuat: Kandang Utama (KDG-001)")

        await session.commit()
        print("\n🎉 Seeding selesai!")
        print("\nAkun yang tersedia:")
        print("  Admin    → admin / admin123")
        print("  Pemilik  → pemilik / pemilik123")
        print("  Peternak → peternak / peternak123")
        print("\n⚠️  Segera ganti semua password setelah login pertama!")


if __name__ == "__main__":
    asyncio.run(seed())
