from sqlalchemy import Column, String, Numeric, ForeignKey, Enum, Text, Date, Integer, Boolean, CheckConstraint
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
    EWS = "ews"
    OTHER = "other"


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class Student(Base):
    __tablename__ = "students"
    
    # Foreign key to user
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), 
                     unique=True, nullable=False, index=True)
    
    # Academic Information
    enrollment_number = Column(String(50), unique=True, nullable=False, index=True)
    university_name = Column(String(255), nullable=False)
    college_name = Column(String(255), nullable=False)
    course_name = Column(String(255), nullable=False)  # B.Tech, MBBS, etc.
    course_duration = Column(Integer, nullable=False)  # in years
    current_year = Column(Integer, nullable=False)  # 1, 2, 3, 4
    specialization = Column(String(255), nullable=True)
    
    # Academic Performance
    current_cgpa = Column(Numeric(4, 2), nullable=True)  # 0.00 to 10.00
    last_semester_percentage = Column(Numeric(5, 2), nullable=True)
    
    # Personal Details
    date_of_birth = Column(Date, nullable=False)
    gender = Column(Enum(Gender), nullable=False)
    caste_category = Column(Enum(CasteCategory), nullable=False)
    
    # Contact Information
    permanent_address = Column(Text, nullable=False)
    current_address = Column(Text, nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    pincode = Column(String(10), nullable=False)
    country = Column(String(50), default="India")
    
    # Family Details
    father_name = Column(String(255), nullable=True)
    mother_name = Column(String(255), nullable=True)
    guardian_name = Column(String(255), nullable=False)
    guardian_phone = Column(String(20), nullable=False)
    guardian_relationship = Column(String(50), nullable=False)
    
    # Financial Information
    family_annual_income = Column(Numeric(12, 2), nullable=False)  # in INR
    monthly_allowance = Column(Numeric(10, 2), nullable=True)
    has_education_loan = Column(Boolean, default=False)
    education_loan_amount = Column(Numeric(12, 2), nullable=True)
    education_loan_emi = Column(Numeric(10, 2), nullable=True)
    
    # Additional Income Sources
    has_part_time_job = Column(Boolean, default=False)
    part_time_income = Column(Numeric(10, 2), nullable=True)
    has_family_business = Column(Boolean, default=False)
    
    # Documents (URLs to cloud storage)
    aadhar_card_url = Column(String(500), nullable=True)
    income_certificate_url = Column(String(500), nullable=True)
    caste_certificate_url = Column(String(500), nullable=True)
    marksheet_10th_url = Column(String(500), nullable=True)
    marksheet_12th_url = Column(String(500), nullable=True)
    college_id_card_url = Column(String(500), nullable=True)
    bank_passbook_url = Column(String(500), nullable=True)
    
    # Financial Metrics (calculated)
    total_expenses_last_month = Column(Numeric(10, 2), default=0.0)
    total_income_last_month = Column(Numeric(10, 2), default=0.0)
    financial_stress_score = Column(Numeric(4, 2), nullable=True)  # 0.00 to 100.00
    dropout_risk_score = Column(Numeric(4, 2), nullable=True)  # 0.00 to 100.00
    last_risk_calculated_at = Column(DateTime(timezone=True), nullable=True)
    
    # Scholarship Stats
    total_scholarships_applied = Column(Integer, default=0)
    total_scholarships_awarded = Column(Integer, default=0)
    total_scholarship_amount = Column(Numeric(12, 2), default=0.0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    profile_completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="student_profile")
    expenses = relationship("Expense", back_populates="student")
    budgets = relationship("Budget", back_populates="student")
    scholarships = relationship("ScholarshipApplication", back_populates="student")
    
    __table_args__ = (
        Index("idx_student_enrollment", "enrollment_number"),
        Index("idx_student_university_course", "university_name", "course_name"),
        Index("idx_student_income", "family_annual_income"),
        Index("idx_student_state_caste", "state", "caste_category"),
        CheckConstraint("current_cgpa >= 0 AND current_cgpa <= 10", 
                       name="check_cgpa_range"),
        CheckConstraint("last_semester_percentage >= 0 AND last_semester_percentage <= 100", 
                       name="check_percentage_range"),
    )
    
    def __repr__(self):
        return f"<Student(id={self.id}, enrollment={self.enrollment_number}, course={self.course_name})>"