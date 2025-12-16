import logging
from typing import Dict, List, Optional
from datetime import datetime
import asyncio
from firebase_admin import messaging
from ..integrations.firebase import firebase_app
from ..models.user import User
from ..schemas.notification import NotificationCreate

logger = logging.getLogger(__name__)


class FCMNotificationHandler:
    def __init__(self):
        self.app = firebase_app
    
    async def send_notification(
        self,
        user: User,
        notification: NotificationCreate,
        data: Optional[Dict] = None
    ) -> bool:
        """Send push notification via FCM"""
        
        # Build message
        message = messaging.Message(
            notification=messaging.Notification(
                title=notification.title,
                body=notification.body,
                image=notification.image_url
            ),
            data=data or {},
            token=user.fcm_token  # Store FCM token during registration
        )
        
        try:
            # Send message
            response = await asyncio.to_thread(
                messaging.send,
                message,
                app=self.app
            )
            
            logger.info(f"FCM notification sent: {response}")
            return True
            
        except messaging.UnregisteredError:
            # Token is no longer valid
            logger.warning(f"FCM token invalid for user {user.id}")
            await self._handle_invalid_token(user)
            return False
            
        except Exception as e:
            logger.error(f"FCM notification failed: {e}")
            return False
    
    async def send_multicast(
        self,
        users: List[User],
        notification: NotificationCreate,
        data: Optional[Dict] = None
    ) -> Dict[str, int]:
        """Send notifications to multiple users efficiently"""
        
        valid_tokens = [
            user.fcm_token for user in users 
            if user.fcm_token and user.notifications_enabled
        ]
        
        if not valid_tokens:
            return {"success": 0, "failure": 0}
        
        # Create multicast message
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=notification.title,
                body=notification.body,
                image=notification.image_url
            ),
            data=data or {},
            tokens=valid_tokens
        )
        
        try:
            response = await asyncio.to_thread(
                messaging.send_multicast,
                message,
                app=self.app
            )
            
            logger.info(f"FCM multicast sent: {response.success_count} success, "
                       f"{response.failure_count} failures")
            
            # Handle failures
            if response.failure_count > 0:
                await self._handle_failed_tokens(users, response.responses)
            
            return {
                "success": response.success_count,
                "failure": response.failure_count
            }
            
        except Exception as e:
            logger.error(f"FCM multicast failed: {e}")
            return {"success": 0, "failure": len(valid_tokens)}
    
    async def _handle_invalid_token(self, user: User):
        """Handle invalid FCM token"""
        # In production, update user record to remove invalid token
        # and trigger re-registration
        pass
    
    async def _handle_failed_tokens(
        self,
        users: List[User],
        responses: List[messaging.SendResponse]
    ):
        """Handle failed token responses"""
        for i, response in enumerate(responses):
            if not response.success:
                user = users[i]
                logger.warning(f"Failed to send to user {user.id}: {response.exception}")
    
    def create_budget_alert(
        self,
        budget_name: str,
        spent_percentage: float,
        remaining_days: int
    ) -> NotificationCreate:
        """Create budget alert notification"""
        
        if spent_percentage >= 0.9:
            title = "⚠️ Budget Critical Alert"
            body = f"'{budget_name}' budget is {spent_percentage:.0%} spent!"
        elif spent_percentage >= 0.8:
            title = "🔔 Budget Alert"
            body = f"'{budget_name}' budget is {spent_percentage:.0%} spent. {remaining_days} days remaining."
        else:
            title = "📊 Budget Update"
            body = f"'{budget_name}' budget is on track: {spent_percentage:.0%} spent."
        
        return NotificationCreate(
            title=title,
            body=body,
            notification_type="budget_alert",
            priority="high" if spent_percentage >= 0.8 else "medium"
        )
    
    def create_scholarship_deadline_alert(
        self,
        scholarship_name: str,
        days_until_deadline: int
    ) -> NotificationCreate:
        """Create scholarship deadline alert"""
        
        if days_until_deadline <= 1:
            title = "⏰ Scholarship Deadline Today!"
            body = f"Apply for '{scholarship_name}' before it closes!"
        elif days_until_deadline <= 3:
            title = "⚠️ Scholarship Deadline Soon"
            body = f"'{scholarship_name}' closes in {days_until_deadline} days!"
        elif days_until_deadline <= 7:
            title = "🔔 Scholarship Reminder"
            body = f"'{scholarship_name}' application due in {days_until_deadline} days."
        else:
            title = "🎓 Scholarship Opportunity"
            body = f"New scholarship match: '{scholarship_name}'"
        
        return NotificationCreate(
            title=title,
            body=body,
            notification_type="scholarship_alert",
            priority="high" if days_until_deadline <= 3 else "medium"
        )


# Singleton instance
fcm_handler = FCMNotificationHandler()