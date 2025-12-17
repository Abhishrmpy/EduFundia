from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List
from datetime import date, datetime
from enum import Enum
import uuid


class BudgetStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    EXCEEDED = "exceeded"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class BudgetPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class BudgetBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    total_amount: float = Field(..., gt=0, le=10000000)  # Max 1 crore
    categories: Dict[str, float] = Field(...)  # {"food": 5000, "transport": 2000}
    period: BudgetPeriod = Field(default=BudgetPeriod.MONTHLY)
    start_date: date
    end_date: date
    alert_threshold: float = Field(default=0.8, ge=0.1, le=1.0)
    
    @validator('end_date')
    def validate_dates(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('End date must be after start date')
        return v
    
    @validator('categories')
    def validate_categories(cls, v):
        total = sum(v.values())
        if abs(total - 100) > 0.01:  # Allow small floating point errors
            raise ValueError('Category amounts must sum to total amount')
        return v


class BudgetCreate(BudgetBase):
    user_id: uuid.UUID
    student_id: uuid.UUID
    ai_generated: bool = Field(default=False)


class BudgetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[BudgetStatus] = None
    alert_threshold: Optional[float] = Field(None, ge=0.1, le=1.0)


class BudgetResponse(BudgetBase):
    id: uuid.UUID
    user_id: uuid.UUID
    student_id: uuid.UUID
    spent_amount: float
    remaining_amount: float
    status: BudgetStatus
    ai_generated: bool
    ai_confidence_score: Optional[float]
    ai_recommendations: Optional[Dict]
    last_alert_sent_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    # Calculated fields
    utilization_percentage: float
    daily_budget: Optional[float]
    days_remaining: int
    is_on_track: bool
    
    class Config:
        from_attributes = True


class BudgetAnalytics(BaseModel):
    budget: BudgetResponse
    category_spending: Dict[str, float]
    category_utilization: Dict[str, float]
    daily_spending_trend: List[Dict[str, float]]
    projected_end_balance: float
    recommendations: List[str]
    alerts: List[str]


class BudgetRecommendation(BaseModel):
    total_amount: float
    categories: Dict[str, float]
    confidence_score: float
    rationale: str
    recommendations: List[str]
    warnings: List[str]