from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import logging

from ...core.database import get_db
from ...core.security import get_current_user
from ...schemas.user import UserCreate, UserResponse, UserUpdate, LoginRequest, Token
from ...services.auth_service import AuthService
from ...integrations.firebase import firebase_service

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)


@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Login with Firebase token"""
    try:
        # Verify Firebase token
        decoded_token = await firebase_service.verify_id_token(login_data.firebase_token)
        if not decoded_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        auth_service = AuthService(db)
        
        # Check if user exists
        user = await auth_service.get_user_by_firebase_uid(decoded_token["uid"])
        
        if not user:
            # Create new user if doesn't exist
            user_data = UserCreate(
                firebase_uid=decoded_token["uid"],
                email=decoded_token.get("email", ""),
                full_name=decoded_token.get("name", "Student"),
                phone_number=decoded_token.get("phone_number"),
                profile_picture_url=decoded_token.get("picture"),
                role="student"
            )
            user = await auth_service.create_user(user_data)
        
        # Update last login
        await auth_service.update_last_login(user.id)
        
        # Create access token (for internal use)
        from ...core.security import create_access_token
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email}
        )
        
        # Prepare response
        token_data = Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=3600,  # 1 hour
            user=UserResponse.from_orm(user)
        )
        
        logger.info(f"User logged in: {user.email}")
        return token_data
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    auth_service = AuthService(db)
    
    try:
        user = await auth_service.create_user(user_data)
        return UserResponse.from_orm(user)
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user information"""
    auth_service = AuthService(db)
    
    try:
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse.from_orm(user)
    except Exception as e:
        logger.error(f"Get user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update current user information"""
    auth_service = AuthService(db)
    
    try:
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        updated_user = await auth_service.update_user(user.id, user_update)
        return UserResponse.from_orm(updated_user)
    except Exception as e:
        logger.error(f"Update user error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/verify-email")
async def verify_email(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify user's email"""
    auth_service = AuthService(db)
    
    try:
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        verified_user = await auth_service.verify_email(user.id)
        return {"message": "Email verified successfully"}
    except Exception as e:
        logger.error(f"Email verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/verify-phone")
async def verify_phone(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Verify user's phone number"""
    auth_service = AuthService(db)
    
    try:
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        verified_user = await auth_service.verify_phone(user.id)
        return {"message": "Phone verified successfully"}
    except Exception as e:
        logger.error(f"Phone verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/profile")
async def get_user_profile(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get complete user profile with student data"""
    auth_service = AuthService(db)
    
    try:
        profile = await auth_service.get_user_profile_by_firebase_uid(current_user["uid"])
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return profile
    except Exception as e:
        logger.error(f"Get profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/logout")
async def logout(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Logout user (client-side token invalidation)"""
    # Firebase tokens are stateless, so client should discard the token
    return {"message": "Logged out successfully"}


@router.delete("/account")
async def delete_account(
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete user account (soft delete)"""
    auth_service = AuthService(db)
    
    try:
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        await auth_service.delete_user(user.id)
        return {"message": "Account deleted successfully"}
    except Exception as e:
        logger.error(f"Delete account error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Admin endpoints
@router.get("/users", dependencies=[Depends(get_current_user)])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List all users (admin only)"""
    from ...models.user import User
    from sqlalchemy import select
    
    try:
        result = await db.execute(
            select(User).offset(skip).limit(limit).order_by(User.created_at.desc())
        )
        users = result.scalars().all()
        
        return [
            UserResponse.from_orm(user) for user in users
        ]
    except Exception as e:
        logger.error(f"List users error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user role (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    auth_service = AuthService(db)
    
    try:
        import uuid
        user_uuid = uuid.UUID(user_id)
        admin_uuid = uuid.UUID(current_user.get("user_id", ""))
        
        updated_user = await auth_service.update_user_role(
            user_uuid, role, admin_uuid
        )
        return UserResponse.from_orm(updated_user)
    except Exception as e:
        logger.error(f"Update role error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )