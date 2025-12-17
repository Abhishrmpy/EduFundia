from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import auth, credentials, exceptions
from jose import JWTError, jwt
import logging

logger = logging.getLogger(__name__)

# Initialize Firebase if credentials are available
firebase_app = None
try:
    from ..core.config import settings
    
    if all([
        settings.firebase_project_id,
        settings.firebase_private_key,
        settings.firebase_client_email
    ]):
        firebase_cred = credentials.Certificate({
            "type": "service_account",
            "project_id": settings.firebase_project_id,
            "private_key": settings.firebase_private_key,
            "client_email": settings.firebase_client_email,
            "token_uri": "https://oauth2.googleapis.com/token"
        })
        firebase_app = firebase_admin.initialize_app(firebase_cred)
        logger.info("Firebase Admin SDK initialized successfully")
    else:
        logger.warning("Firebase credentials not provided, authentication will be mocked")
except Exception as e:
    logger.warning(f"Firebase initialization failed: {e}")


class FirebaseAuth:
    """Firebase JWT authentication"""
    
    def __init__(self):
        self.security = HTTPBearer(auto_error=False)
    
    async def __call__(
        self,
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer())
    ) -> Dict[str, Any]:
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        try:
            # Verify Firebase JWT token
            decoded_token = auth.verify_id_token(
                credentials.credentials,
                check_revoked=True
            )
            
            return {
                "uid": decoded_token.get("uid"),
                "email": decoded_token.get("email"),
                "phone_number": decoded_token.get("phone_number"),
                "email_verified": decoded_token.get("email_verified", False),
                "name": decoded_token.get("name"),
                "picture": decoded_token.get("picture"),
                "role": decoded_token.get("role", "student"),
            }
        
        except exceptions.ExpiredIdTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            )
        except exceptions.InvalidIdTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        except exceptions.RevokedIdTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revoked",
            )
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            
            # Fallback for development without Firebase
            if settings.environment == "development":
                logger.warning("Using mock authentication for development")
                return {
                    "uid": "mock_uid_123",
                    "email": "student@example.com",
                    "email_verified": True,
                    "role": "student",
                }
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
            )


class RoleChecker:
    """Role-based access control"""
    
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles
    
    def __call__(self, user: Dict = Depends(FirebaseAuth())):
        if user.get("role") not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user


# Create dependencies
get_current_user = FirebaseAuth()
allow_student = RoleChecker(["student"])
allow_admin = RoleChecker(["admin"])
allow_all = RoleChecker(["student", "admin"])


def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None):
    """Create JWT token for internal use"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
    return encoded_jwt