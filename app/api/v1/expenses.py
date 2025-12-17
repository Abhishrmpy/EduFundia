from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import date
import uuid
import logging
import tempfile
import os

from ...core.database import get_db
from ...core.security import get_current_user
from ...schemas.expense import ExpenseCreate, ExpenseUpdate, ExpenseResponse, ExpenseFilter, ExpenseSummary
from ...services.auth_service import AuthService
from ...services.expense_service import ExpenseService
from ...utils.file_utils import file_utils

router = APIRouter(prefix="/expenses", tags=["expenses"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(
    expense_data: ExpenseCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new expense"""
    auth_service = AuthService(db)
    expense_service = ExpenseService(db)
    
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
        expense_data.user_id = user.id
        expense_data.student_id = student.id
        
        # Create expense
        expense = await expense_service.create_expense(expense_data)
        return ExpenseResponse.from_orm(expense)
        
    except Exception as e:
        logger.error(f"Create expense error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/upload", response_model=ExpenseResponse)
async def upload_expense_with_receipt(
    title: str = Query(..., description="Expense title"),
    amount: float = Query(..., gt=0, description="Expense amount"),
    category: str = Query(..., description="Expense category"),
    expense_date: date = Query(..., description="Expense date"),
    description: Optional[str] = Query(None, description="Expense description"),
    payment_method: Optional[str] = Query(None, description="Payment method"),
    receipt: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload expense with receipt image"""
    auth_service = AuthService(db)
    expense_service = ExpenseService(db)
    
    try:
        # Validate file
        if not receipt.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file uploaded"
            )
        
        # Validate file type
        allowed_types = ["image/jpeg", "image/png", "image/jpg", "application/pdf"]
        mime_type = file_utils.get_file_mime_type_from_buffer(await receipt.read())
        await receipt.seek(0)  # Reset file pointer
        
        if mime_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type {mime_type} not allowed. Allowed: {', '.join(allowed_types)}"
            )
        
        # Validate file size (max 10MB)
        max_size_mb = 10
        file_size = len(await receipt.read())
        await receipt.seek(0)
        
        if file_size > max_size_mb * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File size exceeds {max_size_mb}MB limit"
            )
        
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
        
        # Save receipt to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_utils.get_file_extension(receipt.filename)) as tmp_file:
            content = await receipt.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Generate unique filename
            unique_filename = file_utils.generate_unique_filename(receipt.filename)
            
            # In production, upload to cloud storage (e.g., Google Cloud Storage, AWS S3)
            # For now, we'll store in a local directory
            upload_dir = "uploads/receipts"
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, unique_filename)
            
            # Move file to upload directory
            import shutil
            shutil.move(tmp_file_path, file_path)
            
            # Create expense with receipt URL
            from ...schemas.expense import ExpenseCategory, PaymentMethod
            
            expense_data = ExpenseCreate(
                user_id=user.id,
                student_id=student.id,
                title=title,
                description=description,
                category=ExpenseCategory(category),
                amount=amount,
                expense_date=expense_date,
                payment_method=PaymentMethod(payment_method) if payment_method else None,
                receipt_url=f"/receipts/{unique_filename}"  # In production, use cloud storage URL
            )
            
            expense = await expense_service.create_expense(expense_data)
            return ExpenseResponse.from_orm(expense)
            
        finally:
            # Cleanup temporary file if it still exists
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
        
    except Exception as e:
        logger.error(f"Upload expense error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=List[ExpenseResponse])
async def get_expenses(
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    category: Optional[str] = Query(None, description="Category filter"),
    min_amount: Optional[float] = Query(None, gt=0, description="Minimum amount"),
    max_amount: Optional[float] = Query(None, gt=0, description="Maximum amount"),
    payment_method: Optional[str] = Query(None, description="Payment method filter"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get expenses with filters"""
    auth_service = AuthService(db)
    expense_service = ExpenseService(db)
    
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
        
        # Parse tags
        tag_list = tags.split(",") if tags else None
        
        # Create filter
        expense_filter = ExpenseFilter(
            start_date=start_date,
            end_date=end_date,
            category=category,
            min_amount=min_amount,
            max_amount=max_amount,
            payment_method=payment_method,
            tags=tag_list
        )
        
        # Get expenses
        expenses = await expense_service.get_student_expenses(
            student_id=student.id,
            filters=expense_filter,
            limit=limit,
            offset=skip
        )
        
        return [ExpenseResponse.from_orm(expense) for expense in expenses]
        
    except Exception as e:
        logger.error(f"Get expenses error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{expense_id}", response_model=ExpenseResponse)
async def get_expense(
    expense_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get specific expense by ID"""
    auth_service = AuthService(db)
    expense_service = ExpenseService(db)
    
    try:
        # Get expense
        expense = await expense_service.get_expense_by_id(expense_id)
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or expense.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this expense"
            )
        
        return ExpenseResponse.from_orm(expense)
        
    except Exception as e:
        logger.error(f"Get expense error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: uuid.UUID,
    expense_update: ExpenseUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update expense"""
    auth_service = AuthService(db)
    expense_service = ExpenseService(db)
    
    try:
        # Get expense
        expense = await expense_service.get_expense_by_id(expense_id)
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or expense.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this expense"
            )
        
        # Update expense
        updated_expense = await expense_service.update_expense(expense_id, expense_update)
        return ExpenseResponse.from_orm(updated_expense)
        
    except Exception as e:
        logger.error(f"Update expense error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(
    expense_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete expense"""
    auth_service = AuthService(db)
    expense_service = ExpenseService(db)
    
    try:
        # Get expense
        expense = await expense_service.get_expense_by_id(expense_id)
        if not expense:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Expense not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or expense.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this expense"
            )
        
        # Delete expense
        await expense_service.delete_expense(expense_id)
        
    except Exception as e:
        logger.error(f"Delete expense error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/summary", response_model=ExpenseSummary)
async def get_expense_summary(
    start_date: Optional[date] = Query(None, description="Start date"),
    end_date: Optional[date] = Query(None, description="End date"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get expense summary and analytics"""
    auth_service = AuthService(db)
    expense_service = ExpenseService(db)
    
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
        
        # Get summary
        summary = await expense_service.get_expense_summary(
            student_id=student.id,
            start_date=start_date,
            end_date=end_date
        )
        
        return summary
        
    except Exception as e:
        logger.error(f"Get expense summary error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/trend")
async def get_expense_trend(
    period_days: int = Query(30, ge=7, le=365, description="Period in days"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get expense spending trend"""
    auth_service = AuthService(db)
    expense_service = ExpenseService(db)
    
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
        
        # Get trend
        trend = await expense_service.get_spending_trend(
            student_id=student.id,
            period_days=period_days
        )
        
        return {
            "student_id": str(student.id),
            "period_days": period_days,
            "trend": trend,
            "total_spent": sum(item["amount"] for item in trend),
            "average_daily": sum(item["amount"] for item in trend) / len(trend) if trend else 0
        }
        
    except Exception as e:
        logger.error(f"Get expense trend error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/insights")
async def get_expense_insights(
    days: int = Query(90, ge=30, le=365, description="Analysis period in days"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get expense insights and recommendations"""
    auth_service = AuthService(db)
    expense_service = ExpenseService(db)
    
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
        
        # Get category insights
        insights = await expense_service.get_category_insights(
            student_id=student.id,
            days=days
        )
        
        # Generate recommendations
        recommendations = []
        
        # Check if entertainment spending is high
        entertainment_spent = 0
        for category in insights.get("categories", []):
            if category["category"] == "entertainment":
                entertainment_spent = category["total_amount"]
                break
        
        monthly_income = student.monthly_allowance or (student.family_annual_income / 12)
        if monthly_income > 0 and entertainment_spent > 0:
            entertainment_percentage = (entertainment_spent / monthly_income) * 100
            if entertainment_percentage > 20:
                recommendations.append("Consider reducing entertainment spending. It's over 20% of your income.")
        
        # Check for transportation optimization
        transport_spent = 0
        for category in insights.get("categories", []):
            if category["category"] == "transport":
                transport_spent = category["total_amount"]
                break
        
        if transport_spent > 2000:  # More than ₹2000 per month
            recommendations.append("Explore student discounts on public transport or consider carpooling to reduce transportation costs.")
        
        # Food spending optimization
        food_spent = 0
        for category in insights.get("categories", []):
            if category["category"] == "food":
                food_spent = category["total_amount"]
                break
        
        if food_spent > 5000:  # More than ₹5000 per month
            recommendations.append("Consider cooking at home more often. Eating out frequently can significantly increase food expenses.")
        
        # Add generic recommendation if none
        if not recommendations:
            if insights.get("total_spent", 0) > 0:
                recommendations.append("Your spending patterns look balanced. Keep tracking expenses regularly.")
            else:
                recommendations.append("Start tracking expenses to get personalized insights.")
        
        return {
            "student_id": str(student.id),
            "analysis_period_days": days,
            "total_spent": insights.get("total_spent", 0),
            "most_frequent_category": insights.get("most_frequent_category"),
            "most_expensive_category": insights.get("most_expensive_category"),
            "category_breakdown": insights.get("categories", []),
            "recommendations": recommendations,
            "monthly_income": monthly_income,
            "savings_potential": monthly_income - (insights.get("total_spent", 0) / (days / 30)) if monthly_income > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Get expense insights error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )