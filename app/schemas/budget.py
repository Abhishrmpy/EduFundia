from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List
from datetime import date
from enum import Enum
import uuid


class BudgetStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    EXCEEDED = "exceeded"
    CANCELLED = "cancelled"


class BudgetCategory(str, Enum):
    TUITION = "tuition"
    HOSTEL = "hostel"
    FOOD = "food"
    TRANSPORT = "transport"
    BOOKS = "books"
    ENTERTAINMENT = "entertainment"
    MEDICAL = "medical"
    SAVINGS = "savings"
    OTHER = "other"


class BudgetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    
    total_amount: float = Field(..., gt=0, le=10000000)  # Up to 1 crore
    categories: Dict[BudgetCategory, float] = Field(...)
    
    start_date: date
    end_date: date
    
    @validator('end_date')
    def validate_dates(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('End date must be after start date')
        return v
    
    @validator('categories')
    def validate_categories(cls, v):
        total = sum(v.values())
        if abs(total - 100) > 0.01:  # Allow small floating point errors
            raise ValueError('Category percentages must sum to 100%')
        return v


class BudgetCreate(BudgetBase):
    student_id: uuid.UUID
    ai_generated: bool = Field(default=False)


class BudgetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    status: Optional[BudgetStatus] = None


class BudgetResponse(BudgetBase):
    id: uuid.UUID
    student_id: uuid.UUID
    spent_amount: float
    remaining_amount: float
    status: BudgetStatus
    ai_generated: bool
    ai_recommendation_score: Optional[float]
    created_at: date
    updated_at: Optional[date]
    
    # Calculated fields
    utilization_percentage: float
    days_remaining: int
    daily_budget: float
    
    class Config:
        from_attributes = True