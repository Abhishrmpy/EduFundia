from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import auth, credentials
from google.oauth2 import id_token
from google.auth.transport import requests
import logging

logger = logging.getLogger(__name__)

# Initialize Firebase
firebase_cred = None
try:
    firebase_cred = credentials.Certificate({
        "type": "service_account",
        "project_id": "your-project-id",
        "private_key": "-----BEGIN PRIVATE KEY-----\n...",
        "client_email": "firebase-adminsdk@project.iam.gserviceaccount.com"
    })
    firebase_admin.initialize_app(firebase_cred)
except Exception as e:
    logger.warning(f"Firebase initialization failed: {e}")


class FirebaseAuth:
    def __init__(self):
        self.security = HTTPBearer(auto_error=False)
    
    async def __call__(
        self, 
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer())
    ) -> Dict[str, Any]:
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer authentication required",
            )
        
        try:
            # Verify Firebase JWT token
            decoded_token = auth.verify_id_token(credentials.credentials)
            
            # Check if token is expired
            current_time = datetime.utcnow().timestamp()
            if decoded_token.get("exp", 0) < current_time:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired",
                )
            
            return {
                "uid": decoded_token.get("uid"),
                "email": decoded_token.get("email"),
                "phone_number": decoded_token.get("phone_number"),
                "email_verified": decoded_token.get("email_verified", False),
                "role": decoded_token.get("role", "student"),
            }
        
        except auth.ExpiredIdTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            )
        except auth.InvalidIdTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
            )


class RoleChecker:
    def __init__(self, allowed_roles: list):
        self.allowed_roles = allowed_roles
    
    def __call__(self, user: dict = Depends(FirebaseAuth())):
        if user.get("role") not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user


# Auth dependency
get_current_user = FirebaseAuth()