import logging
from typing import Optional, Dict, Any
import firebase_admin
from firebase_admin import auth, credentials, messaging, exceptions
from ..core.config import settings

logger = logging.getLogger(__name__)

# Firebase app instance
firebase_app = None


class FirebaseService:
    """Firebase integration service"""
    
    def __init__(self):
        self._initialize_firebase()
    
    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        global firebase_app
        
        if firebase_app is not None:
            return firebase_app
        
        try:
            # Check if Firebase credentials are provided
            if not all([
                settings.firebase_project_id,
                settings.firebase_private_key,
                settings.firebase_client_email
            ]):
                logger.warning("Firebase credentials not provided. Using mock mode.")
                return None
            
            # Initialize Firebase
            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": settings.firebase_project_id,
                "private_key": settings.firebase_private_key.replace("\\n", "\n"),
                "client_email": settings.firebase_client_email,
                "token_uri": "https://oauth2.googleapis.com/token"
            })
            
            firebase_app = firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin SDK initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            firebase_app = None
        
        return firebase_app
    
    async def verify_id_token(self, id_token: str) -> Optional[Dict[str, Any]]:
        """Verify Firebase ID token"""
        if not firebase_app:
            logger.warning("Firebase not initialized, returning mock token")
            # Return mock user for development
            return {
                "uid": "mock_uid_123",
                "email": "student@example.com",
                "email_verified": True,
                "name": "Mock Student",
                "picture": None,
                "role": "student"
            }
        
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token
        except exceptions.ExpiredIdTokenError:
            logger.error("Firebase token expired")
            return None
        except exceptions.InvalidIdTokenError:
            logger.error("Invalid Firebase token")
            return None
        except Exception as e:
            logger.error(f"Error verifying Firebase token: {e}")
            return None
    
    async def get_user(self, uid: str) -> Optional[Dict[str, Any]]:
        """Get user from Firebase by UID"""
        if not firebase_app:
            return None
        
        try:
            user = auth.get_user(uid)
            return {
                "uid": user.uid,
                "email": user.email,
                "email_verified": user.email_verified,
                "phone_number": user.phone_number,
                "display_name": user.display_name,
                "photo_url": user.photo_url,
                "disabled": user.disabled,
            }
        except exceptions.UserNotFoundError:
            logger.error(f"Firebase user not found: {uid}")
            return None
        except Exception as e:
            logger.error(f"Error getting Firebase user: {e}")
            return None
    
    async def create_user(
        self,
        email: str,
        password: str,
        display_name: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Create a new user in Firebase"""
        if not firebase_app:
            # Mock user creation for development
            return {
                "uid": f"mock_uid_{email}",
                "email": email,
                "email_verified": False,
                "display_name": display_name
            }
        
        try:
            user = auth.create_user(
                email=email,
                password=password,
                display_name=display_name
            )
            
            logger.info(f"Created Firebase user: {user.uid}")
            return {
                "uid": user.uid,
                "email": user.email,
                "email_verified": user.email_verified,
                "display_name": user.display_name,
            }
        except exceptions.EmailAlreadyExistsError:
            logger.error(f"Email already exists: {email}")
            return None
        except Exception as e:
            logger.error(f"Error creating Firebase user: {e}")
            return None
    
    async def update_user(
        self,
        uid: str,
        email: Optional[str] = None,
        display_name: Optional[str] = None,
        phone_number: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Update Firebase user"""
        if not firebase_app:
            return None
        
        try:
            update_args = {}
            if email:
                update_args["email"] = email
            if display_name:
                update_args["display_name"] = display_name
            if phone_number:
                update_args["phone_number"] = phone_number
            
            user = auth.update_user(uid, **update_args)
            return {
                "uid": user.uid,
                "email": user.email,
                "display_name": user.display_name,
                "phone_number": user.phone_number,
            }
        except Exception as e:
            logger.error(f"Error updating Firebase user: {e}")
            return None
    
    async def delete_user(self, uid: str) -> bool:
        """Delete Firebase user"""
        if not firebase_app:
            return True  # Mock success
        
        try:
            auth.delete_user(uid)
            logger.info(f"Deleted Firebase user: {uid}")
            return True
        except Exception as e:
            logger.error(f"Error deleting Firebase user: {e}")
            return False
    
    async def send_push_notification(
        self,
        user_id: str,
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None
    ) -> bool:
        """Send push notification via Firebase Cloud Messaging"""
        if not firebase_app:
            logger.warning("Firebase not initialized, skipping push notification")
            return True  # Mock success
        
        try:
            # In production, you would get the FCM token from user's device
            # For now, we'll simulate or use a placeholder
            
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=token or "mock_fcm_token",  # Replace with actual token
            )
            
            response = messaging.send(message)
            logger.info(f"Sent FCM notification: {response}")
            return True
            
        except exceptions.UnregisteredError:
            logger.warning(f"FCM token invalid for user {user_id}")
            return False
        except Exception as e:
            logger.error(f"Error sending FCM notification: {e}")
            return False
    
    async def send_multicast_notification(
        self,
        user_tokens: List[str],
        title: str,
        body: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, int]:
        """Send multicast push notification"""
        if not firebase_app or not user_tokens:
            return {"success": 0, "failure": 0}
        
        try:
            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                tokens=user_tokens,
            )
            
            response = messaging.send_multicast(message)
            
            result = {
                "success": response.success_count,
                "failure": response.failure_count,
            }
            
            logger.info(f"Sent multicast FCM notification: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error sending multicast FCM notification: {e}")
            return {"success": 0, "failure": len(user_tokens)}
    
    async def verify_phone_number(self, phone_number: str) -> Optional[str]:
        """Start phone number verification (simulated)"""
        # In production, integrate with Firebase Phone Auth
        # For now, return a mock verification ID
        logger.info(f"Phone verification requested for: {phone_number}")
        return f"mock_verification_id_{phone_number}"
    
    async def verify_phone_code(
        self,
        verification_id: str,
        code: str
    ) -> Optional[str]:
        """Verify phone number with code (simulated)"""
        # In production, complete Firebase Phone Auth
        # For now, always succeed in development
        logger.info(f"Phone code verification: {verification_id}, code: {code}")
        return "mock_phone_auth_token"


# Singleton instance
firebase_service = FirebaseService()