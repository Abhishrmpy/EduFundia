from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import uuid
import logging

from ..models.user import User, UserRole
from ..schemas.user import UserCreate, UserUpdate
from ..core.exceptions import NotFoundError, ConflictError

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_user_by_firebase_uid(self, firebase_uid: str) -> Optional[User]:
        """Get user by Firebase UID"""
        result = await self.db.execute(
            select(User).where(User.firebase_uid == firebase_uid)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        """Get user by ID"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user"""
        # Check if user already exists
        existing_user = await self.get_user_by_firebase_uid(user_data.firebase_uid)
        if existing_user:
            raise ConflictError("User already exists")
        
        # Check if email is already used
        existing_email = await self.get_user_by_email(user_data.email)
        if existing_email:
            raise ConflictError("Email already registered")
        
        # Create new user
        user = User(
            firebase_uid=user_data.firebase_uid,
            email=user_data.email,
            full_name=user_data.full_name,
            phone_number=user_data.phone_number,
            profile_picture_url=user_data.profile_picture_url,
            role=user_data.role,
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"Created new user: {user.email} (ID: {user.id})")
        return user
    
    async def update_user(
        self, 
        user_id: uuid.UUID, 
        update_data: UserUpdate
    ) -> User:
        """Update user information"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User")
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(user, field, value)
        
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"Updated user: {user.email}")
        return user
    
    async def update_last_login(self, user_id: uuid.UUID) -> None:
        """Update user's last login timestamp"""
        await self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                last_login_at=func.now(),
                login_count=User.login_count + 1
            )
        )
        await self.db.commit()
    
    async def verify_email(self, user_id: uuid.UUID) -> User:
        """Mark user's email as verified"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User")
        
        user.email_verified = True
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"Email verified for user: {user.email}")
        return user
    
    async def verify_phone(self, user_id: uuid.UUID) -> User:
        """Mark user's phone as verified"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User")
        
        user.phone_verified = True
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"Phone verified for user: {user.email}")
        return user
    
    async def update_user_role(
        self, 
        user_id: uuid.UUID, 
        new_role: UserRole,
        admin_user_id: uuid.UUID
    ) -> User:
        """Update user role (admin only)"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User")
        
        # Check if admin is trying to change their own role
        if user_id == admin_user_id:
            raise ValueError("Cannot change your own role")
        
        user.role = new_role
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"Updated role for user {user.email} to {new_role}")
        return user
    
    async def delete_user(self, user_id: uuid.UUID) -> bool:
        """Soft delete a user"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise NotFoundError("User")
        
        user.is_active = False
        await self.db.commit()
        
        logger.info(f"Soft deleted user: {user.email}")
        return True
    
    async def get_user_profile(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Get complete user profile with student data"""
        from ..models.student import Student
        
        result = await self.db.execute(
            select(User, Student)
            .outerjoin(Student, User.id == Student.user_id)
            .where(User.id == user_id)
        )
        row = result.first()
        
        if not row:
            raise NotFoundError("User")
        
        user, student = row
        return {
            "user": user,
            "student": student
        }