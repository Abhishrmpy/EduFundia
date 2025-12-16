from sqlalchemy import Column, String, Numeric, ForeignKey, Enum, Text, Date, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from .base import Base
import uuid


class ExpenseCategory(str, enum.Enum):
    TUITION_FEES = "tuition_fees"
    HOSTEL_FEES = "hostel_fees"
    FOOD = "food"
    TRANSPORT = "transport"
    BOOKS = "books"
    ENTERTAINMENT = "entertainment"
    MEDICAL = "medical"
    OTHER = "other"


class TransactionType(str, enum.Enum):
    EXPENSE = "expense"
    INCOME = "income"


class Expense(Base):
    __tablename__ = "expenses"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    
    # Transaction Details
    transaction_type = Column(Enum(TransactionType), nullable=False)
    category = Column(Enum(ExpenseCategory), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="INR")
    
    # Description
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Date & Time
    transaction_date = Column(Date, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Payment Details
    payment_method = Column(String(50), nullable=True)  # cash, upi, card, etc.
    reference_number = Column(String(100), nullable=True, unique=True)
    
    # Metadata
    tags = Column(JSONB, default=list)  # e.g., ["urgent", "educational"]
    receipt_url = Column(String(500), nullable=True)  # GCS URL
    
    # Recurring Expenses
    is_recurring = Column(Boolean, default=False)
    recurrence_frequency = Column(String(20), nullable=True)  # monthly, weekly, etc.
    recurrence_end_date = Column(Date, nullable=True)
    
    # Relationships
    student = relationship("Student", back_populates="expenses")
    
    __table_args__ = (
        Index("idx_expense_student_date", "student_id", "transaction_date"),
        Index("idx_expense_category", "category"),
        Index("idx_expense_amount", "amount"),
        CheckConstraint("amount > 0", name="check_amount_positive"),
    )