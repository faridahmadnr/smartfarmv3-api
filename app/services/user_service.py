import uuid
from typing import Optional, List

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, UserRole
from app.core.security import get_password_hash
from app.schemas.user import UserCreate, UserUpdate


class UserService:
    """Service for user-related operations."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_id(
        self,
        user_id: uuid.UUID,
        include_peternaks: bool = False,
    ) -> Optional[User]:
        """Get user by ID."""
        query = select(User).where(User.id == user_id)
        
        if include_peternaks:
            query = query.options(selectinload(User.peternaks))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        query = select(User).where(User.username == username)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_username_or_email(self, identifier: str) -> Optional[User]:
        """Get user by username or email."""
        query = select(User).where(
            or_(User.username == identifier, User.email == identifier)
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_list(
        self,
        page: int = 1,
        per_page: int = 10,
        role: Optional[UserRole] = None,
        pemilik_id: Optional[uuid.UUID] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> tuple[List[User], int]:
        """Get paginated list of users with filters."""
        query = select(User)
        count_query = select(func.count(User.id))
        
        # Apply filters
        if role:
            query = query.where(User.role == role)
            count_query = count_query.where(User.role == role)
        
        if pemilik_id:
            query = query.where(User.pemilik_id == pemilik_id)
            count_query = count_query.where(User.pemilik_id == pemilik_id)
        
        if is_active is not None:
            query = query.where(User.is_active == is_active)
            count_query = count_query.where(User.is_active == is_active)
        
        if search:
            search_filter = or_(
                User.username.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)
        
        # Get total count
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()
        
        # Apply pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page).order_by(User.created_at.desc())
        
        result = await self.db.execute(query)
        users = result.scalars().all()
        
        return list(users), total
    
    async def create(
        self,
        user_data: UserCreate,
        created_by_id: Optional[uuid.UUID] = None,
    ) -> User:
        """Create a new user."""
        user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=get_password_hash(user_data.password),
            full_name=user_data.full_name,
            phone=user_data.phone,
            role=user_data.role,
            pemilik_id=user_data.pemilik_id,
            created_by_id=created_by_id,
        )
        
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        
        return user
    
    async def update(
        self,
        user: User,
        user_data: UserUpdate,
    ) -> User:
        """Update an existing user."""
        update_data = user_data.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(user, field, value)
        
        await self.db.flush()
        await self.db.refresh(user)
        
        return user
    
    async def update_password(self, user: User, new_password: str) -> User:
        """Update user password."""
        user.hashed_password = get_password_hash(new_password)
        await self.db.flush()
        await self.db.refresh(user)
        return user
    
    async def update_refresh_token(
        self,
        user: User,
        refresh_token: Optional[str],
        expires_at: Optional[any],
    ) -> User:
        """Update user's refresh token."""
        user.refresh_token = refresh_token
        user.refresh_token_expires_at = expires_at
        await self.db.flush()
        await self.db.refresh(user)
        return user
    
    async def deactivate(self, user: User) -> User:
        """Soft delete (deactivate) a user."""
        user.is_active = False
        await self.db.flush()
        await self.db.refresh(user)
        return user
    
    async def get_peternaks_by_pemilik(
        self,
        pemilik_id: uuid.UUID,
        is_active: Optional[bool] = None,
    ) -> List[User]:
        """Get all peternaks belonging to a pemilik."""
        query = select(User).where(
            User.pemilik_id == pemilik_id,
            User.role == UserRole.PETERNAK,
        )
        
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
