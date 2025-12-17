from sqlalchemy import Column, String, Boolean, DateTime, Enum, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .base import Base
import uuid


class UserRole(str, enum.Enum):
    STUDENT = "student"
    ADMIN = "admin"
    FINANCE_OFFICER = "finance_officer"


class User(Base):
    __tablename__ = "users"
    
    # Firebase UID from authentication
    firebase_uid = Column(String(128), unique=True, nullable=False, index=True)
    
    # Basic info
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone_number = Column(String(20), nullable=True)
    full_name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.STUDENT, nullable=False)
    
    # Profile
    profile_picture_url = Column(String(500), nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    gender = Column(String(20), nullable=True)
    
    # Verification status
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    profile_completed = Column(Boolean, default=False)
    
    # Preferences
    notifications_enabled = Column(Boolean, default=True)
    email_notifications = Column(Boolean, default=True)
    push_notifications = Column(Boolean, default=True)
    
    # Settings
    currency = Column(String(3), default="INR")
    language = Column(String(10), default="en")
    timezone = Column(String(50), default="Asia/Kolkata")
    
    # Security
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    login_count = Column(Integer, default=0)
    
    # Metadata
    metadata_ = Column("metadata", JSONB, default=dict)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    student_profile = relationship("Student", back_populates="user", uselist=False)
    expenses = relationship("Expense", back_populates="user")
    budgets = relationship("Budget", back_populates="user")
    
    __table_args__ = (
        Index("idx_user_email_role", "email", "role"),
        Index("idx_user_created_at", "created_at"),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"