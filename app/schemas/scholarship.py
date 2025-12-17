from pydantic import BaseModel, Field, validator, HttpUrl
from typing import Optional, List, Dict
from datetime import date, datetime
from enum import Enum
import uuid


class ScholarshipType(str, Enum):
    GOVERNMENT = "government"
    STATE = "state"
    UNIVERSITY = "university"
    PRIVATE = "private"
    CORPORATE = "corporate"
    NGO = "ngo"
    INTERNATIONAL = "international"


class ScholarshipStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"
    ARCHIVED = "archived"


class ScholarshipBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    scholarship_type: ScholarshipType
    provider_name: str = Field(..., min_length=1, max_length=255)
    provider_website: Optional[HttpUrl] = None
    
    # Amount
    amount: Optional[float] = Field(None, gt=0)
    min_amount: Optional[float] = Field(None, gt=0)
    max_amount: Optional[float] = Field(None, gt=0)
    is_variable: bool = Field(default=False)
    currency: str = Field(default="INR")
    
    # Eligibility
    eligibility_criteria: Dict = Field(default_factory=dict)
    min_income: Optional[float] = Field(None, gt=0)
    max_income: Optional[float] = Field(None, gt=0)
    eligible_castes: Optional[List[str]] = None
    eligible_genders: Optional[List[str]] = None
    eligible_courses: Optional[List[str]] = None
    eligible_states: Optional[List[str]] = None
    min_percentage: Optional[float] = Field(None, ge=0, le=100)
    min_cgpa: Optional[float] = Field(None, ge=0, le=10)
    
    # Application
    application_url: Optional[HttpUrl] = None
    application_fee: float = Field(default=0.0, ge=0)
    documents_required: Optional[List[str]] = None
    
    # Dates
    application_start_date: date
    application_end_date: date
    result_date: Optional[date] = None
    disbursement_date: Optional[date] = None
    
    @validator('application_end_date')
    def validate_dates(cls, v, values):
        if 'application_start_date' in values and v <= values['application_start_date']:
            raise ValueError('Application end date must be after start date')
        return v


class ScholarshipCreate(ScholarshipBase):
    pass


class ScholarshipUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    status: Optional[ScholarshipStatus] = None
    is_featured: Optional[bool] = None


class ScholarshipResponse(ScholarshipBase):
    id: uuid.UUID
    status: ScholarshipStatus
    total_applications: int
    total_awarded: int
    popularity_score: float
    tags: List[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ScholarshipMatch(BaseModel):
    scholarship: ScholarshipResponse
    match_score: float = Field(..., ge=0, le=1)
    eligibility_score: float = Field(..., ge=0, le=1)
    reasons: List[str]
    documents_needed: List[str]
    deadline_days: int
    application_status: str


class ScholarshipFilter(BaseModel):
    scholarship_type: Optional[ScholarshipType] = None
    min_amount: Optional[float] = Field(None, gt=0)
    max_amount: Optional[float] = Field(None, gt=0)
    eligible_caste: Optional[str] = None
    eligible_gender: Optional[str] = None
    eligible_course: Optional[str] = None
    eligible_state: Optional[str] = None
    application_deadline_soon: Optional[bool] = None
    is_featured: Optional[bool] = None
    search_query: Optional[str] = None