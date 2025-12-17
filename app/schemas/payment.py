from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
from enum import Enum
import uuid


class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    UPI = "upi"
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    NET_BANKING = "net_banking"
    WALLET = "wallet"
    BANK_TRANSFER = "bank_transfer"
    CASH = "cash"
    SCHOLARSHIP = "scholarship"
    LOAN = "loan"


class PaymentType(str, Enum):
    TUITION_FEE = "tuition_fee"
    HOSTEL_FEE = "hostel_fee"
    EXAM_FEE = "exam_fee"
    LIBRARY_FEE = "library_fee"
    OTHER_FEE = "other_fee"
    EXPENSE = "expense"
    REFUND = "refund"


class PaymentBase(BaseModel):
    amount: float = Field(..., gt=0, le=10000000)  # Max 1 crore
    currency: str = Field(default="INR")
    payment_type: PaymentType
    description: Optional[str] = None
    recipient_name: str = Field(..., min_length=1, max_length=255)
    recipient_account: Optional[str] = Field(None, min_length=1, max_length=100)
    payment_method: PaymentMethod
    gateway_name: Optional[str] = None


class PaymentCreate(PaymentBase):
    user_id: uuid.UUID
    student_id: uuid.UUID


class PaymentUpdate(BaseModel):
    status: Optional[PaymentStatus] = None
    gateway_reference: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class PaymentResponse(PaymentBase):
    id: uuid.UUID
    user_id: uuid.UUID
    student_id: uuid.UUID
    payment_reference: str
    status: PaymentStatus
    gateway_reference: Optional[str]
    gateway_fee: float
    tax_amount: float
    net_amount: float
    payment_date: datetime
    processed_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_code: Optional[str]
    error_message: Optional[str]
    verification_status: Optional[str]
    verified_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class PaymentSimulation(BaseModel):
    amount: float = Field(..., gt=0)
    payment_method: PaymentMethod
    upi_id: Optional[str] = Field(None, pattern=r'^[\w.-]+@[\w]+$')
    card_number: Optional[str] = Field(None, pattern=r'^\d{16}$')
    card_expiry: Optional[str] = Field(None, pattern=r'^\d{2}/\d{2}$')
    card_cvv: Optional[str] = Field(None, pattern=r'^\d{3,4}$')
    bank_account: Optional[str] = None
    ifsc_code: Optional[str] = Field(None, pattern=r'^[A-Z]{4}0[A-Z0-9]{6}$')


class PaymentWebhook(BaseModel):
    payment_reference: str
    status: PaymentStatus
    gateway_reference: str
    gateway_name: str
    verified: bool = Field(default=False)
    signature: Optional[str] = None