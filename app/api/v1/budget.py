from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import date
import uuid
import logging

from ...core.database import get_db
from ...core.security import get_current_user
from ...schemas.budget import BudgetCreate, BudgetUpdate, BudgetResponse, BudgetAnalytics, BudgetRecommendation
from ...services.auth_service import AuthService
from ...services.budget_service import BudgetService
from ...services.notification_service import NotificationService

router = APIRouter(prefix="/budgets", tags=["budgets"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_budget(
    budget_data: BudgetCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Create a new budget"""
    auth_service = AuthService(db)
    budget_service = BudgetService(db)
    
    try:
        # Get user and student
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        from ...models.student import Student
        from sqlalchemy import select
        
        result = await db.execute(
            select(Student).where(Student.user_id == user.id)
        )
        student = result.scalar_one_or_none()
        
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found"
            )
        
        # Set user and student IDs
        budget_data.user_id = user.id
        budget_data.student_id = student.id
        
        # Create budget
        budget = await budget_service.create_budget(budget_data)
        
        # Schedule budget notifications in background
        if background_tasks:
            background_tasks.add_task(
                schedule_budget_notifications,
                budget.id,
                user.id
            )
        
        return BudgetResponse.from_orm(budget)
        
    except Exception as e:
        logger.error(f"Create budget error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/ai-recommendation", response_model=BudgetResponse)
async def generate_ai_budget(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Generate AI-powered budget recommendation"""
    auth_service = AuthService(db)
    budget_service = BudgetService(db)
    
    try:
        # Get user and student
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        from ...models.student import Student
        from sqlalchemy import select
        
        result = await db.execute(
            select(Student).where(Student.user_id == user.id)
        )
        student = result.scalar_one_or_none()
        
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found"
            )
        
        # Generate AI recommendation
        recommendation = await budget_service.generate_ai_budget_recommendation(student.id)
        
        # Create budget from recommendation
        from datetime import date, timedelta
        
        budget_data = BudgetCreate(
            user_id=user.id,
            student_id=student.id,
            name=f"AI Recommended Budget - {date.today().strftime('%B %Y')}",
            description="AI-generated budget based on your spending patterns and financial situation",
            total_amount=recommendation.total_amount,
            categories=recommendation.categories,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            ai_generated=True
        )
        
        # Create budget
        budget = await budget_service.create_budget(budget_data)
        
        # Store AI metadata
        budget.ai_confidence_score = recommendation.confidence_score
        budget.ai_recommendations = {
            "rationale": recommendation.rationale,
            "recommendations": recommendation.recommendations,
            "warnings": recommendation.warnings
        }
        await db.commit()
        
        # Schedule notifications
        if background_tasks:
            background_tasks.add_task(
                schedule_budget_notifications,
                budget.id,
                user.id
            )
        
        return BudgetResponse.from_orm(budget)
        
    except Exception as e:
        logger.error(f"Generate AI budget error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=List[BudgetResponse])
async def get_budgets(
    status: Optional[str] = Query(None, description="Budget status filter"),
    date_from: Optional[date] = Query(None, description="Start date filter"),
    date_to: Optional[date] = Query(None, description="End date filter"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get budgets with optional filters"""
    auth_service = AuthService(db)
    budget_service = BudgetService(db)
    
    try:
        # Get user and student
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        from ...models.student import Student
        from sqlalchemy import select
        
        result = await db.execute(
            select(Student).where(Student.user_id == user.id)
        )
        student = result.scalar_one_or_none()
        
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found"
            )
        
        # Get budgets
        budgets = await budget_service.get_student_budgets(
            student_id=student.id,
            status=status,
            date_from=date_from,
            date_to=date_to
        )
        
        return [BudgetResponse.from_orm(budget) for budget in budgets]
        
    except Exception as e:
        logger.error(f"Get budgets error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/current", response_model=BudgetResponse)
async def get_current_budget(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current active budget"""
    auth_service = AuthService(db)
    budget_service = BudgetService(db)
    
    try:
        # Get user and student
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        from ...models.student import Student
        from sqlalchemy import select
        
        result = await db.execute(
            select(Student).where(Student.user_id == user.id)
        )
        student = result.scalar_one_or_none()
        
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found"
            )
        
        # Get current (active) budget
        from ...models.budget import BudgetStatus
        budgets = await budget_service.get_student_budgets(
            student_id=student.id,
            status=BudgetStatus.ACTIVE
        )
        
        if not budgets:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active budget found"
            )
        
        # Return the most recent active budget
        current_budget = budgets[0]
        return BudgetResponse.from_orm(current_budget)
        
    except Exception as e:
        logger.error(f"Get current budget error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{budget_id}", response_model=BudgetResponse)
async def get_budget(
    budget_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get specific budget by ID"""
    auth_service = AuthService(db)
    budget_service = BudgetService(db)
    
    try:
        # Get budget
        budget = await budget_service.get_budget_by_id(budget_id)
        if not budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Budget not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or budget.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this budget"
            )
        
        return BudgetResponse.from_orm(budget)
        
    except Exception as e:
        logger.error(f"Get budget error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: uuid.UUID,
    budget_update: BudgetUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update budget"""
    auth_service = AuthService(db)
    budget_service = BudgetService(db)
    
    try:
        # Get budget
        budget = await budget_service.get_budget_by_id(budget_id)
        if not budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Budget not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or budget.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this budget"
            )
        
        # Update budget
        updated_budget = await budget_service.update_budget(budget_id, budget_update)
        return BudgetResponse.from_orm(updated_budget)
        
    except Exception as e:
        logger.error(f"Update budget error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete budget (soft delete)"""
    auth_service = AuthService(db)
    budget_service = BudgetService(db)
    
    try:
        # Get budget
        budget = await budget_service.get_budget_by_id(budget_id)
        if not budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Budget not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or budget.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this budget"
            )
        
        # Delete budget
        await budget_service.delete_budget(budget_id)
        
    except Exception as e:
        logger.error(f"Delete budget error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{budget_id}/analytics", response_model=BudgetAnalytics)
async def get_budget_analytics(
    budget_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get budget analytics and insights"""
    auth_service = AuthService(db)
    budget_service = BudgetService(db)
    
    try:
        # Get budget
        budget = await budget_service.get_budget_by_id(budget_id)
        if not budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Budget not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or budget.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this budget"
            )
        
        # Get analytics
        analytics = await budget_service.get_budget_analytics(budget_id)
        return analytics
        
    except Exception as e:
        logger.error(f"Get budget analytics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{budget_id}/refresh")
async def refresh_budget_spending(
    budget_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Refresh budget spending calculations"""
    auth_service = AuthService(db)
    budget_service = BudgetService(db)
    
    try:
        # Get budget
        budget = await budget_service.get_budget_by_id(budget_id)
        if not budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Budget not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or budget.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this budget"
            )
        
        # Update spending
        updated_budget = await budget_service.update_budget_spending(budget_id)
        
        return {
            "message": "Budget spending updated successfully",
            "budget": BudgetResponse.from_orm(updated_budget)
        }
        
    except Exception as e:
        logger.error(f"Refresh budget error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{budget_id}/alerts")
async def get_budget_alerts(
    budget_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get budget alerts and notifications"""
    auth_service = AuthService(db)
    budget_service = BudgetService(db)
    
    try:
        # Get budget
        budget = await budget_service.get_budget_by_id(budget_id)
        if not budget:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Budget not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or budget.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this budget"
            )
        
        # Check for alerts
        alerts = await budget_service.check_budget_alerts(budget_id)
        
        return {
            "budget_id": str(budget_id),
            "budget_name": budget.name,
            "alerts": alerts,
            "total_alerts": len(alerts)
        }
        
    except Exception as e:
        logger.error(f"Get budget alerts error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/recommendation/ai", response_model=BudgetRecommendation)
async def get_ai_recommendation_only(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get AI budget recommendation without creating budget"""
    auth_service = AuthService(db)
    budget_service = BudgetService(db)
    
    try:
        # Get user and student
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        from ...models.student import Student
        from sqlalchemy import select
        
        result = await db.execute(
            select(Student).where(Student.user_id == user.id)
        )
        student = result.scalar_one_or_none()
        
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found"
            )
        
        # Generate AI recommendation only
        recommendation = await budget_service.generate_ai_budget_recommendation(student.id)
        return recommendation
        
    except Exception as e:
        logger.error(f"Get AI recommendation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


async def schedule_budget_notifications(budget_id: uuid.UUID, user_id: uuid.UUID):
    """Background task to schedule budget notifications"""
    # This would be implemented with Celery or similar task queue
    # For now, it's a placeholder for the notification scheduling logic
    
    # In production, you would:
    # 1. Schedule daily check for budget alerts
    # 2. Send notifications via FCM/email
    # 3. Update notification records
    
    logger.info(f"Scheduled notifications for budget {budget_id}, user {user_id}")
    pass