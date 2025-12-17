from sqlalchemy import Column, String, Numeric, ForeignKey, Enum, Text, Date, DateTime, Boolean, CheckConstraint
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
    ARCHIVED = "archived"


class BudgetPeriod(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"


class Budget(Base):
    __tablename__ = "budgets"
    
    # Foreign keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Budget details
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Amounts
    total_amount = Column(Numeric(10, 2), nullable=False)
    spent_amount = Column(Numeric(10, 2), default=0.0)
    remaining_amount = Column(Numeric(10, 2), default=0.0)
    
    # Categories breakdown
    categories = Column(JSONB, nullable=False)  # {"food": 5000, "transport": 2000, ...}
    
    # Period
    period = Column(Enum(BudgetPeriod), default=BudgetPeriod.MONTHLY)
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False, index=True)
    
    # Status
    status = Column(Enum(BudgetStatus), default=BudgetStatus.ACTIVE)
    
    # AI Features
    ai_generated = Column(Boolean, default=False)
    ai_confidence_score = Column(Numeric(3, 2), nullable=True)  # 0.00 to 1.00
    ai_recommendations = Column(JSONB, nullable=True)
    
    # Notifications
    alert_threshold = Column(Numeric(3, 2), default=0.8)  # Alert at 80% spent
    last_alert_sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Tracking
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="budgets")
    student = relationship("Student", back_populates="budgets")
    expenses = relationship("Expense", back_populates="budget")
    
    __table_args__ = (
        Index("idx_budget_student_status", "student_id", "status"),
        Index("idx_budget_period", "start_date", "end_date"),
        CheckConstraint("total_amount > 0", name="check_total_amount_positive"),
        CheckConstraint("spent_amount <= total_amount", name="check_spent_leq_total"),
        CheckConstraint("remaining_amount = total_amount - spent_amount", 
                       name="check_remaining_calculation"),
    )
    
    def __repr__(self):
        return f"<Budget(id={self.id}, name={self.name}, spent={self.spent_amount}/{self.total_amount})>"