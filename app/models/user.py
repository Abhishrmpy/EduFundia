from sqlalchemy import Column, String, Boolean, DateTime, Enum, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
import enum
from datetime import datetime
from .base import Base
import uuid


class UserRole(str, enum.Enum):
    STUDENT = "student"
    ADMIN = "admin"
    FINANCE_OFFICER = "finance_officer"


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firebase_uid = Column(String(128), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone_number = Column(String(20), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.STUDENT, nullable=False)
    
    # Profile
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    profile_picture_url = Column(String(500), nullable=True)
    
    # Verification
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    metadata_ = Column("metadata", JSONB, default=dict)
    
    __table_args__ = (
        Index("idx_user_email_role", "email", "role"),
        Index("idx_user_firebase_uid", "firebase_uid"),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"