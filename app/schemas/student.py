from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Dict
from datetime import date
from enum import Enum
import uuid


class CasteCategory(str, Enum):
    GENERAL = "general"
    OBC = "obc"
    SC = "sc"
    ST = "st"
    OTHER = "other"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class StudentBase(BaseModel):
    university: str = Field(..., min_length=1, max_length=255)
    college: str = Field(..., min_length=1, max_length=255)
    course: str = Field(..., min_length=1, max_length=255)
    specialization: Optional[str] = Field(None, max_length=255)
    year_of_study: str = Field(..., pattern=r'^(1st|2nd|3rd|4th|5th|6th|7th|8th)$')
    enrollment_number: str = Field(..., min_length=5, max_length=50)
    
    date_of_birth: date
    gender: Gender
    caste_category: CasteCategory
    
    home_state: str = Field(..., min_length=1, max_length=100)
    home_district: str = Field(..., min_length=1, max_length=100)
    current_city: str = Field(..., min_length=1, max_length=100)
    pincode: str = Field(..., pattern=r'^\d{6}$')
    
    family_annual_income: float = Field(..., gt=0, le=100000000)  # Up to 10 crore
    monthly_allowance: Optional[float] = Field(None, gt=0)
    has_education_loan: bool = Field(default=False)
    loan_amount: Optional[float] = Field(None, gt=0)
    
    emergency_contact_name: str = Field(..., min_length=1, max_length=200)
    emergency_contact_phone: str = Field(..., pattern=r'^\+?1?\d{9,15}$')
    emergency_contact_relation: str = Field(..., min_length=1, max_length=50)


class StudentCreate(StudentBase):
    user_id: uuid.UUID


class StudentUpdate(BaseModel):
    university: Optional[str] = Field(None, min_length=1, max_length=255)
    college: Optional[str] = Field(None, min_length=1, max_length=255)
    monthly_allowance: Optional[float] = Field(None, gt=0)
    current_city: Optional[str] = Field(None, min_length=1, max_length=100)
    pincode: Optional[str] = Field(None, pattern=r'^\d{6}$')
    
    @validator('monthly_allowance')
    def validate_allowance(cls, v):
        if v is not None and v > 1000000:  # 10 lakh max
            raise ValueError('Monthly allowance too high')
        return v


class StudentResponse(StudentBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: date
    updated_at: Optional[date]
    
    # Calculated fields
    financial_stress_score: Optional[float] = Field(None, ge=0, le=1)
    dropout_risk_score: Optional[float] = Field(None, ge=0, le=1)
    
    class Config:
        from_attributes = True