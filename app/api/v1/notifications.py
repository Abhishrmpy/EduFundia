from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid
import logging

from ...core.database import get_db
from ...core.security import get_current_user
from ...schemas.notification import NotificationResponse, NotificationUpdate, NotificationPreferences
from ...services.auth_service import AuthService
from ...services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[NotificationResponse])
async def get_notifications(
    unread_only: bool = Query(False, description="Show only unread notifications"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's notifications"""
    auth_service = AuthService(db)
    notification_service = NotificationService(db)
    
    try:
        # Get user
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get notifications
        notifications = await notification_service.get_user_notifications(
            user_id=user.id,
            unread_only=unread_only,
            limit=limit,
            offset=skip
        )
        
        return [NotificationResponse.from_orm(notification) for notification in notifications]
        
    except Exception as e:
        logger.error(f"Get notifications error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get specific notification"""
    auth_service = AuthService(db)
    notification_service = NotificationService(db)
    
    try:
        # Get notification
        notification = await notification_service.get_notification_by_id(notification_id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or notification.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this notification"
            )
        
        return NotificationResponse.from_orm(notification)
        
    except Exception as e:
        logger.error(f"Get notification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark notification as read"""
    auth_service = AuthService(db)
    notification_service = NotificationService(db)
    
    try:
        # Get notification
        notification = await notification_service.get_notification_by_id(notification_id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or notification.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this notification"
            )
        
        # Mark as read
        updated_notification = await notification_service.mark_as_read(notification_id)
        return NotificationResponse.from_orm(updated_notification)
        
    except Exception as e:
        logger.error(f"Mark notification as read error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/mark-all-read")
async def mark_all_notifications_as_read(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark all notifications as read"""
    auth_service = AuthService(db)
    notification_service = NotificationService(db)
    
    try:
        # Get user
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Mark all as read
        updated_count = await notification_service.mark_all_as_read(user.id)
        
        return {
            "message": f"Marked {updated_count} notifications as read",
            "updated_count": updated_count
        }
        
    except Exception as e:
        logger.error(f"Mark all notifications as read error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete notification"""
    auth_service = AuthService(db)
    notification_service = NotificationService(db)
    
    try:
        # Get notification
        notification = await notification_service.get_notification_by_id(notification_id)
        if not notification:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or notification.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this notification"
            )
        
        # Delete notification
        await notification_service.delete_notification(notification_id)
        
    except Exception as e:
        logger.error(f"Delete notification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/preferences")
async def get_notification_preferences(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get user's notification preferences"""
    auth_service = AuthService(db)
    
    try:
        # Get user
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {
            "email_notifications": user.email_notifications,
            "push_notifications": user.push_notifications,
            "sms_notifications": False,  # Not implemented yet
            "budget_alerts": True,  # Default
            "scholarship_alerts": True,  # Default
            "fee_reminders": True,  # Default
            "risk_alerts": True,  # Default
            "marketing_emails": False,  # Default
            "notifications_enabled": user.notifications_enabled
        }
        
    except Exception as e:
        logger.error(f"Get notification preferences error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/preferences")
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update notification preferences"""
    auth_service = AuthService(db)
    notification_service = NotificationService(db)
    
    try:
        # Get user
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update preferences
        updated_user = await notification_service.update_notification_preferences(
            user_id=user.id,
            preferences=preferences
        )
        
        return {
            "message": "Notification preferences updated successfully",
            "preferences": {
                "email_notifications": updated_user.email_notifications,
                "push_notifications": updated_user.push_notifications,
                "notifications_enabled": updated_user.notifications_enabled
            }
        }
        
    except Exception as e:
        logger.error(f"Update notification preferences error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/stats")
async def get_notification_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get notification statistics"""
    auth_service = AuthService(db)
    notification_service = NotificationService(db)
    
    try:
        # Get user
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get stats
        stats = await notification_service.get_notification_stats(user.id)
        
        return {
            "user_id": str(user.id),
            "total_notifications": stats["total_notifications"],
            "unread_notifications": stats["unread_notifications"],
            "read_percentage": stats["read_percentage"],
            "notifications_by_type": stats["notifications_by_type"]
        }
        
    except Exception as e:
        logger.error(f"Get notification stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/test")
async def send_test_notification(
    notification_type: str = Query("budget_alert", description="Notification type"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a test notification (for development)"""
    auth_service = AuthService(db)
    notification_service = NotificationService(db)
    
    try:
        # Get user
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Create test notification based on type
        from ...schemas.notification import NotificationCreate, NotificationType, NotificationPriority
        from datetime import datetime
        
        test_notifications = {
            "budget_alert": NotificationCreate(
                user_id=user.id,
                title="💰 Budget Alert",
                message="Your monthly budget is 80% spent. ₹2,000 remaining for the next 10 days.",
                notification_type=NotificationType.BUDGET_ALERT,
                priority=NotificationPriority.HIGH,
                data={
                    "budget_name": "Monthly Budget",
                    "spent_percentage": 0.8,
                    "remaining_amount": 2000,
                    "remaining_days": 10
                }
            ),
            "scholarship_deadline": NotificationCreate(
                user_id=user.id,
                title="🎓 Scholarship Deadline",
                message="Apply for 'Merit Scholarship' before it closes in 3 days!",
                notification_type=NotificationType.SCHOLARSHIP_DEADLINE,
                priority=NotificationPriority.HIGH,
                data={
                    "scholarship_name": "Merit Scholarship",
                    "days_until_deadline": 3,
                    "amount": 50000
                }
            ),
            "fee_reminder": NotificationCreate(
                user_id=user.id,
                title="📅 Fee Reminder",
                message="Tuition fee payment due in 5 days. Amount: ₹25,000",
                notification_type=NotificationType.FEE_REMINDER,
                priority=NotificationPriority.MEDIUM,
                data={
                    "fee_name": "Tuition Fee",
                    "amount": 25000,
                    "due_date": datetime.now().isoformat(),
                    "days_until_due": 5
                }
            ),
            "risk_alert": NotificationCreate(
                user_id=user.id,
                title="⚠️ Financial Risk Alert",
                message="High financial stress detected. Consider applying for emergency aid.",
                notification_type=NotificationType.RISK_ALERT,
                priority=NotificationPriority.CRITICAL,
                data={
                    "risk_score": 85,
                    "recommendations": ["Apply for scholarships", "Reduce discretionary spending"]
                }
            )
        }
        
        if notification_type not in test_notifications:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid notification type. Allowed: {', '.join(test_notifications.keys())}"
            )
        
        # Send test notification
        notification = await notification_service.create_notification(
            test_notifications[notification_type]
        )
        
        return {
            "message": "Test notification sent successfully",
            "notification": NotificationResponse.from_orm(notification)
        }
        
    except Exception as e:
        logger.error(f"Send test notification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )