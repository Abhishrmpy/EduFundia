from sqlalchemy import Column, String, Numeric, ForeignKey, Enum, Text, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .base import Base
import uuid


class CasteCategory(str, enum.Enum):
    GENERAL = "general"
    OBC = "obc"
    SC = "sc"
    ST = "st"
    OTHER = "other"


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class Student(Base):
    __tablename__ = "students"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), 
                     unique=True, nullable=False, index=True)
    
    # Academic Details
    university = Column(String(255), nullable=False)
    college = Column(String(255), nullable=False)
    course = Column(String(255), nullable=False)  # B.Tech, MBBS, etc.
    specialization = Column(String(255), nullable=True)
    year_of_study = Column(String(10), nullable=False)  # 1st, 2nd, etc.
    enrollment_number = Column(String(50), unique=True, nullable=False, index=True)
    
    # Personal & Demographic
    date_of_birth = Column(Date, nullable=False)
    gender = Column(Enum(Gender), nullable=False)
    caste_category = Column(Enum(CasteCategory), nullable=False)
    
    # Location
    home_state = Column(String(100), nullable=False)
    home_district = Column(String(100), nullable=False)
    current_city = Column(String(100), nullable=False)
    pincode = Column(String(10), nullable=False)
    
    # Financial Details
    family_annual_income = Column(Numeric(12, 2), nullable=False)  # in INR
    monthly_allowance = Column(Numeric(10, 2), nullable=True)
    has_education_loan = Column(Boolean, default=False)
    loan_amount = Column(Numeric(12, 2), nullable=True)
    
    # Emergency Contact
    emergency_contact_name = Column(String(200), nullable=False)
    emergency_contact_phone = Column(String(20), nullable=False)
    emergency_contact_relation = Column(String(50), nullable=False)
    
    # Documents (stored in Google Cloud Storage)
    aadhar_card_url = Column(String(500), nullable=True)
    income_certificate_url = Column(String(500), nullable=True)
    caste_certificate_url = Column(String(500), nullable=True)
    marksheet_url = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", backref="student_profile", lazy="joined")
    expenses = relationship("Expense", back_populates="student", cascade="all, delete-orphan")
    budgets = relationship("Budget", back_populates="student", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_student_enrollment", "enrollment_number"),
        Index("idx_student_course_income", "course", "family_annual_income"),
        Index("idx_student_location", "home_state", "current_city"),
    )