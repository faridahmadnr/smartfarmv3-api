"""
Script to create the first admin user.
Run this after setting up the database.

Usage:
    python create_admin.py
"""
import asyncio
import sys

# Add app to path
sys.path.insert(0, ".")

from app.database import async_session_maker, create_tables
from app.models.user import User, UserRole
from app.core.security import get_password_hash


async def create_admin(
    email: str = "admin@smartfarm.com",
    username: str = "admin",
    password: str = "admin123",
    full_name: str = "Administrator",
):
    """Create an admin user."""
    # Create tables first
    await create_tables()
    
    async with async_session_maker() as session:
        # Check if admin already exists
        from sqlalchemy import select
        
        existing = await session.execute(
            select(User).where(User.username == username)
        )
        if existing.scalar_one_or_none():
            print(f"❌ User '{username}' already exists!")
            return
        
        # Create admin user
        admin = User(
            email=email,
            username=username,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            role=UserRole.ADMIN,
        )
        session.add(admin)
        await session.commit()
        
        print(f"✅ Admin user created successfully!")
        print(f"   Email: {email}")
        print(f"   Username: {username}")
        print(f"   Password: {password}")
        print(f"\n   ⚠️  Please change the password after first login!")


if __name__ == "__main__":
    asyncio.run(create_admin())
