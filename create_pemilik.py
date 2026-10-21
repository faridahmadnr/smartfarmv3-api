import asyncio
from app.database import async_session_maker
from app.models.user import User, UserRole
from app.core.security import get_password_hash

async def create_pemilik():
    async with async_session_maker() as session:
        pemilik = User(
            email="pemilik@smartfarm.com",
            username="pemilik1",
            hashed_password=get_password_hash("pemilik123"),
            full_name="Suwasto Pemilik",
            role=UserRole.PEMILIK, # Mengunci hak akses murni sebagai Pemilik Kandang
        )
        session.add(pemilik)
        await session.commit()
        print("Akun Pemilik sukses terdaftar langsung di database!")

asyncio.run(create_pemilik())
