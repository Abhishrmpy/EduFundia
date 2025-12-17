from sqlalchemy import Column, String, Numeric, ForeignKey, Enum, Text, Date, DateTime, Boolean, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .base import Base
import uuid


class ExpenseCategory(str, enum.Enum):
    TUITION_FEE = "tuition_fee"
    HOSTEL_FEE = "hostel_fee"
    MESS_FEE = "mess_fee"
    BOOKS = "books"
    STATIONERY = "stationery"
    TRANSPORT = "transport"
    FOOD = "food"
    ENTERTAINMENT = "entertainment"
    MEDICAL = "medical"
    CLOTHING = "clothing"
    COMMUNICATION = "communication"
    PERSONAL_CARE = "personal_care"
    OTHER = "other"


class PaymentMethod(str, enum.Enum):
    CASH = "cash"
    UPI = "upi"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    NET_BANKING = "net_banking"
    SCHOLARSHIP = "scholarship"
    LOAN = "loan"
    OTHER = "other"


class Expense(Base):
    __tablename__ = "expenses"
    
    # Foreign keys
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    budget_id = Column(UUID(as_uuid=True), ForeignKey("budgets.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Expense details
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(Enum(ExpenseCategory), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="INR")
    
    # Payment details
    payment_method = Column(Enum(PaymentMethod), nullable=True)
    payment_reference = Column(String(100), nullable=True)
    is_recurring = Column(Boolean, default=False)
    recurrence_frequency = Column(String(20), nullable=True)  # daily, weekly, monthly
    
    # Date information
    expense_date = Column(Date, nullable=False, index=True)
    transaction_date = Column(DateTime(timezone=True), server_default=func.now())
    
    # Receipt/Proof
    receipt_url = Column(String(500), nullable=True)
    receipt_verified = Column(Boolean, default=False)
    
    # Location data
    location = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    
    # Tags for categorization
    tags = Column(JSONB, default=list)
    
    # Status
    is_verified = Column(Boolean, default=True)
    needs_review = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="expenses")
    student = relationship("Student", back_populates="expenses")
    budget = relationship("Budget", back_populates="expenses")
    
    __table_args__ = (
        Index("idx_expense_student_date", "student_id", "expense_date"),
        Index("idx_expense_category_date", "category", "expense_date"),
        Index("idx_expense_budget", "budget_id", "expense_date"),
        CheckConstraint("amount > 0", name="check_amount_positive"),
    )
    
    def __repr__(self):
        return f"<Expense(id={self.id}, amount={self.amount}, category={self.category})>"