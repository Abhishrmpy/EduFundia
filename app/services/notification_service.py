from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update
from sqlalchemy.orm import selectinload
import uuid
import logging
import asyncio

from ..models.notification import Notification, NotificationType, NotificationPriority
from ..models.user import User
from ..schemas.notification import NotificationCreate, NotificationUpdate, NotificationPreferences
from ..core.exceptions import NotFoundError
from ..integrations.firebase import firebase_service

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_notification(self, notification_data: NotificationCreate) -> Notification:
        """Create a new notification"""
        # Check if user exists
        user_result = await self.db.execute(
            select(User).where(User.id == notification_data.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise NotFoundError("User")
        
        # Create notification
        notification = Notification(
            user_id=notification_data.user_id,
            title=notification_data.title,
            message=notification_data.message,
            notification_type=notification_data.notification_type,
            priority=notification_data.priority,
            data=notification_data.data,
            channels=notification_data.channels or ["in_app"],
        )
        
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)
        
        # Send notification via configured channels
        await self._send_notification(notification, user)
        
        logger.info(f"Created notification: {notification.title} for user {user.email}")
        return notification
    
    async def _send_notification(self, notification: Notification, user: User):
        """Send notification through configured channels"""
        try:
            # Send via Firebase Cloud Messaging (push notification)
            if "push" in notification.channels and user.push_notifications:
                await firebase_service.send_push_notification(
                    user_id=user.id,
                    title=notification.title,
                    body=notification.message,
                    data=notification.data
                )
                notification.push_sent = True
            
            # Send via email (simulated)
            if "email" in notification.channels and user.email_notifications:
                # Here you would integrate with an email service
                # For now, just mark as sent
                notification.email_sent = True
            
            # Send via SMS (simulated)
            if "sms" in notification.channels and user.phone_number:
                # Here you would integrate with an SMS service
                notification.sms_sent = True
            
            notification.is_sent = True
            notification.sent_at = datetime.utcnow()
            await self.db.commit()
            
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            notification.error_message = str(e)
            await self.db.commit()
    
    async def get_notification_by_id(self, notification_id: uuid.UUID) -> Optional[Notification]:
        """Get notification by ID"""
        result = await self.db.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_notifications(
        self,
        user_id: uuid.UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> List[Notification]:
        """Get notifications for a user"""
        query = select(Notification).where(Notification.user_id == user_id)
        
        if unread_only:
            query = query.where(Notification.is_read == False)
        
        query = query.order_by(Notification.created_at.desc())
        query = query.offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def mark_as_read(self, notification_id: uuid.UUID) -> Notification:
        """Mark a notification as read"""
        notification = await self.get_notification_by_id(notification_id)
        if not notification:
            raise NotFoundError("Notification")
        
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(notification)
        
        return notification
    
    async def mark_all_as_read(self, user_id: uuid.UUID) -> int:
        """Mark all notifications as read for a user"""
        result = await self.db.execute(
            update(Notification)
            .where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False
                )
            )
            .values(
                is_read=True,
                read_at=datetime.utcnow()
            )
            .returning(Notification.id)
        )
        
        updated_count = len(result.scalars().all())
        await self.db.commit()
        
        logger.info(f"Marked {updated_count} notifications as read for user {user_id}")
        return updated_count
    
    async def delete_notification(self, notification_id: uuid.UUID) -> bool:
        """Delete a notification"""
        notification = await self.get_notification_by_id(notification_id)
        if not notification:
            raise NotFoundError("Notification")
        
        await self.db.delete(notification)
        await self.db.commit()
        
        logger.info(f"Deleted notification: {notification.title}")
        return True
    
    async def create_budget_alert(
        self,
        user_id: uuid.UUID,
        budget_name: str,
        spent_percentage: float,
        remaining_days: int
    ) -> Notification:
        """Create a budget alert notification"""
        if spent_percentage >= 0.9:
            title = "⚠️ Budget Critical Alert"
            message = f"Your budget '{budget_name}' is {spent_percentage:.0%} spent! You have {remaining_days} days remaining."
            priority = NotificationPriority.CRITICAL
        elif spent_percentage >= 0.8:
            title = "🔔 Budget Alert"
            message = f"Your budget '{budget_name}' is {spent_percentage:.0%} spent. {remaining_days} days remaining."
            priority = NotificationPriority.HIGH
        else:
            title = "📊 Budget Update"
            message = f"Your budget '{budget_name}' is on track: {spent_percentage:.0%} spent."
            priority = NotificationPriority.MEDIUM
        
        notification_data = NotificationCreate(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=NotificationType.BUDGET_ALERT,
            priority=priority,
            data={
                "budget_name": budget_name,
                "spent_percentage": spent_percentage,
                "remaining_days": remaining_days,
                "alert_type": "budget"
            }
        )
        
        return await self.create_notification(notification_data)
    
    async def create_scholarship_deadline_alert(
        self,
        user_id: uuid.UUID,
        scholarship_name: str,
        days_until_deadline: int
    ) -> Notification:
        """Create a scholarship deadline alert"""
        if days_until_deadline <= 1:
            title = "⏰ Scholarship Deadline Today!"
            message = f"Apply for '{scholarship_name}' before it closes today!"
            priority = NotificationPriority.CRITICAL
        elif days_until_deadline <= 3:
            title = "⚠️ Scholarship Deadline Soon"
            message = f"'{scholarship_name}' closes in {days_until_deadline} days!"
            priority = NotificationPriority.HIGH
        elif days_until_deadline <= 7:
            title = "🔔 Scholarship Reminder"
            message = f"'{scholarship_name}' application due in {days_until_deadline} days."
            priority = NotificationPriority.MEDIUM
        else:
            title = "🎓 Scholarship Opportunity"
            message = f"New scholarship match: '{scholarship_name}'"
            priority = NotificationPriority.LOW
        
        notification_data = NotificationCreate(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=NotificationType.SCHOLARSHIP_DEADLINE,
            priority=priority,
            data={
                "scholarship_name": scholarship_name,
                "days_until_deadline": days_until_deadline,
                "alert_type": "scholarship"
            }
        )
        
        return await self.create_notification(notification_data)
    
    async def create_fee_reminder(
        self,
        user_id: uuid.UUID,
        fee_name: str,
        amount: float,
        due_date: datetime
    ) -> Notification:
        """Create a fee payment reminder"""
        days_until_due = (due_date.date() - datetime.utcnow().date()).days
        
        if days_until_due <= 0:
            title = "⚠️ Fee Payment Overdue!"
            message = f"Your {fee_name} fee of ₹{amount:.2f} is overdue!"
            priority = NotificationPriority.CRITICAL
        elif days_until_due <= 3:
            title = "⏰ Fee Payment Due Soon"
            message = f"Your {fee_name} fee of ₹{amount:.2f} is due in {days_until_due} days."
            priority = NotificationPriority.HIGH
        elif days_until_due <= 7:
            title = "🔔 Fee Reminder"
            message = f"Your {fee_name} fee of ₹{amount:.2f} is due in {days_until_due} days."
            priority = NotificationPriority.MEDIUM
        else:
            title = "📅 Upcoming Fee Payment"
            message = f"Your {fee_name} fee of ₹{amount:.2f} is due on {due_date.strftime('%d %b %Y')}."
            priority = NotificationPriority.LOW
        
        notification_data = NotificationCreate(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=NotificationType.FEE_REMINDER,
            priority=priority,
            data={
                "fee_name": fee_name,
                "amount": amount,
                "due_date": due_date.isoformat(),
                "days_until_due": days_until_due
            }
        )
        
        return await self.create_notification(notification_data)
    
    async def get_notification_stats(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """Get notification statistics for a user"""
        # Total notifications
        total_result = await self.db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id
            )
        )
        total = total_result.scalar() or 0
        
        # Unread notifications
        unread_result = await self.db.execute(
            select(func.count(Notification.id)).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.is_read == False
                )
            )
        )
        unread = unread_result.scalar() or 0
        
        # Notifications by type (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        type_result = await self.db.execute(
            select(
                Notification.notification_type,
                func.count(Notification.id).label("count")
            ).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.created_at >= thirty_days_ago
                )
            ).group_by(Notification.notification_type)
        )
        
        by_type = {}
        for row in type_result:
            by_type[row[0].value] = row[1]
        
        return {
            "total_notifications": total,
            "unread_notifications": unread,
            "notifications_by_type": by_type,
            "read_percentage": ((total - unread) / total * 100) if total > 0 else 0
        }
    
    async def cleanup_old_notifications(self, days_old: int = 90) -> int:
        """Delete notifications older than specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        result = await self.db.execute(
            select(Notification).where(
                Notification.created_at < cutoff_date
            )
        )
        old_notifications = list(result.scalars().all())
        
        for notification in old_notifications:
            await self.db.delete(notification)
        
        await self.db.commit()
        
        deleted_count = len(old_notifications)
        logger.info(f"Cleaned up {deleted_count} notifications older than {days_old} days")
        
        return deleted_count
    
    async def update_notification_preferences(
        self,
        user_id: uuid.UUID,
        preferences: NotificationPreferences
    ) -> User:
        """Update user's notification preferences"""
        user_result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            raise NotFoundError("User")
        
        # Update preferences
        user.email_notifications = preferences.email_notifications
        user.push_notifications = preferences.push_notifications
        user.notifications_enabled = any([
            preferences.email_notifications,
            preferences.push_notifications,
            preferences.sms_notifications
        ])
        
        await self.db.commit()
        await self.db.refresh(user)
        
        logger.info(f"Updated notification preferences for user {user.email}")
        return user