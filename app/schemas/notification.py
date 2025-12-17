from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class NotificationType(str, Enum):
    BUDGET_ALERT = "budget_alert"
    SCHOLARSHIP_DEADLINE = "scholarship_deadline"
    FEE_REMINDER = "fee_reminder"
    PAYMENT_REMINDER = "payment_reminder"
    SCHOLARSHIP_MATCH = "scholarship_match"
    RISK_ALERT = "risk_alert"
    SYSTEM = "system"
    OTHER = "other"


class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    notification_type: NotificationType
    priority: NotificationPriority = Field(default=NotificationPriority.MEDIUM)
    data: Optional[Dict[str, Any]] = None
    channels: Optional[List[str]] = Field(default=["in_app"])


class NotificationCreate(NotificationBase):
    user_id: uuid.UUID


class NotificationResponse(NotificationBase):
    id: uuid.UUID
    user_id: uuid.UUID
    is_read: bool
    is_sent: bool
    sent_at: Optional[datetime]
    read_at: Optional[datetime]
    email_sent: bool
    push_sent: bool
    sms_sent: bool
    expires_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True


class NotificationUpdate(BaseModel):
    is_read: Optional[bool] = None


class NotificationPreferences(BaseModel):
    email_notifications: bool = Field(default=True)
    push_notifications: bool = Field(default=True)
    sms_notifications: bool = Field(default=False)
    budget_alerts: bool = Field(default=True)
    scholarship_alerts: bool = Field(default=True)
    fee_reminders: bool = Field(default=True)
    risk_alerts: bool = Field(default=True)
    marketing_emails: bool = Field(default=False)