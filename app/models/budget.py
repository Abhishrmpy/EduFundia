from sqlalchemy import Column, String, Numeric, ForeignKey, Enum, Date, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .base import Base
import uuid


class BudgetStatus(str, enum.Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    EXCEEDED = "exceeded"
    CANCELLED = "cancelled"


class Budget(Base):
    __tablename__ = "budgets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    
    # Budget Details
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Amount & Period
    total_amount = Column(Numeric(10, 2), nullable=False)
    spent_amount = Column(Numeric(10, 2), default=0.0)
    remaining_amount = Column(Numeric(10, 2), default=0.0)
    
    # Categories
    categories = Column(JSONB, nullable=False)  # {"food": 5000, "transport": 2000, ...}
    
    # Time Period
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    
    # Status
    status = Column(Enum(BudgetStatus), default=BudgetStatus.ACTIVE)
    
    # AI Recommendations
    ai_generated = Column(Boolean, default=False)
    ai_recommendation_score = Column(Numeric(3, 2), nullable=True)  # 0-1 score
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Notifications
    last_notified_at = Column(DateTime(timezone=True), nullable=True)
    notification_threshold = Column(Numeric(3, 2), default=0.8)  # Notify at 80% spent
    
    # Relationships
    student = relationship("Student", back_populates="budgets")
    
    __table_args__ = (
        Index("idx_budget_student_status", "student_id", "status"),
        Index("idx_budget_period", "start_date", "end_date"),
        CheckConstraint("total_amount > 0", name="check_total_amount_positive"),
        CheckConstraint("spent_amount <= total_amount", name="check_spent_leq_total"),
        CheckConstraint("remaining_amount = total_amount - spent_amount", 
                       name="check_remaining_calculation"),
    )