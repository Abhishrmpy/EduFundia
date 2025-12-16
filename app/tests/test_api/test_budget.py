from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date, timedelta
import uuid

from ...core.database import get_db
from ...core.security import get_current_user, RoleChecker
from ...models.budget import Budget, BudgetStatus
from ...models.expense import Expense
from ...schemas.budget import BudgetCreate, BudgetUpdate, BudgetResponse
from ...services.budget_service import BudgetService
from ...services.notification_service import NotificationService
from ...integrations.vertex_ai import vertex_ai_client

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.post("/", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
async def create_budget(
    budget_data: BudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    background_tasks: BackgroundTasks = None
):
    """Create a new budget for the student"""
    
    # Verify student owns the budget
    if str(budget_data.student_id) != current_user.get("student_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create budget for another student"
        )
    
    budget_service = BudgetService(db)
    
    # Check for overlapping budgets
    overlapping = await budget_service.check_overlapping_budgets(
        student_id=budget_data.student_id,
        start_date=budget_data.start_date,
        end_date=budget_data.end_date
    )
    
    if overlapping:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Budget overlaps with existing active budget"
        )
    
    # Create budget
    budget = await budget_service.create_budget(budget_data)
    
    # Schedule budget check notifications
    if background_tasks:
        background_tasks.add_task(
            schedule_budget_notifications,
            budget.id,
            budget.student_id
        )
    
    return budget


@router.post("/ai-recommendation", response_model=BudgetResponse)
async def generate_ai_budget(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Generate AI-powered budget recommendation"""
    
    budget_service = BudgetService(db)
    
    # Get student data
    student = await budget_service.get_student_profile(current_user["uid"])
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Get recent expenses
    three_months_ago = date.today() - timedelta(days=90)
    expenses = await budget_service.get_student_expenses(
        student_id=student.id,
        start_date=three_months_ago
    )
    
    # Get historical budgets
    historical_budgets = await budget_service.get_historical_budgets(student.id)
    
    # Generate AI recommendation
    ai_recommendation = await vertex_ai_client.generate_budget_recommendation(
        student=student,
        expenses=expenses,
        historical_budgets=historical_budgets
    )
    
    # Convert to budget schema
    budget_data = BudgetCreate(
        student_id=student.id,
        name=f"AI Recommended Budget - {date.today().strftime('%B %Y')}",
        description="AI-generated budget based on your spending patterns",
        total_amount=ai_recommendation["total_monthly_budget"],
        categories={
            category: data["amount"]
            for category, data in ai_recommendation["categories"].items()
        },
        start_date=date.today(),
        end_date=date.today() + timedelta(days=30),
        ai_generated=True
    )
    
    # Create the budget
    budget = await budget_service.create_budget(budget_data)
    
    # Store AI metadata
    budget.ai_recommendation_score = ai_recommendation.get("ai_confidence_score", 0.8)
    await db.commit()
    
    return budget


@router.get("/", response_model=List[BudgetResponse])
async def get_budgets(
    status: Optional[BudgetStatus] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get student's budgets with optional filters"""
    
    budget_service = BudgetService(db)
    
    # Get student ID
    student = await budget_service.get_student_profile(current_user["uid"])
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    budgets = await budget_service.get_student_budgets(
        student_id=student.id,
        status=status,
        date_from=date_from,
        date_to=date_to
    )
    
    return budgets


@router.get("/{budget_id}", response_model=BudgetResponse)
async def get_budget(
    budget_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get specific budget by ID"""
    
    budget_service = BudgetService(db)
    budget = await budget_service.get_budget_by_id(budget_id)
    
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    
    # Verify ownership
    student = await budget_service.get_student_profile(current_user["uid"])
    if not student or budget.student_id != student.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this budget"
        )
    
    return budget


@router.put("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: uuid.UUID,
    budget_update: BudgetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update budget details"""
    
    budget_service = BudgetService(db)
    
    # Get and verify budget
    budget = await budget_service.get_budget_by_id(budget_id)
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    
    student = await budget_service.get_student_profile(current_user["uid"])
    if not student or budget.student_id != student.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this budget"
        )
    
    # Update budget
    updated_budget = await budget_service.update_budget(budget_id, budget_update)
    
    return updated_budget


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a budget (soft delete by marking as cancelled)"""
    
    budget_service = BudgetService(db)
    
    budget = await budget_service.get_budget_by_id(budget_id)
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    
    student = await budget_service.get_student_profile(current_user["uid"])
    if not student or budget.student_id != student.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this budget"
        )
    
    await budget_service.cancel_budget(budget_id)


@router.get("/{budget_id}/analytics")
async def get_budget_analytics(
    budget_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get detailed analytics for a budget"""
    
    budget_service = BudgetService(db)
    
    budget = await budget_service.get_budget_by_id(budget_id)
    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Budget not found"
        )
    
    # Verify ownership
    student = await budget_service.get_student_profile(current_user["uid"])
    if not student or budget.student_id != student.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this budget"
        )
    
    # Get analytics
    analytics = await budget_service.get_budget_analytics(budget_id)
    
    return {
        "budget": budget,
        "analytics": analytics,
        "recommendations": await budget_service.get_budget_recommendations(budget)
    }


async def schedule_budget_notifications(budget_id: uuid.UUID, student_id: uuid.UUID):
    """Background task to schedule budget notifications"""
    # This would be implemented with Celery or similar task queue
    # For now, it's a placeholder for the notification scheduling logic
    pass