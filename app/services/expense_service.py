from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import selectinload
import uuid
import logging

from ..models.expense import Expense, ExpenseCategory
from ..models.budget import Budget
from ..models.student import Student
from ..schemas.expense import ExpenseCreate, ExpenseUpdate, ExpenseFilter, ExpenseSummary
from ..core.exceptions import NotFoundError, ValidationError

logger = logging.getLogger(__name__)


class ExpenseService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_expense(self, expense_data: ExpenseCreate) -> Expense:
        """Create a new expense"""
        # Validate date
        if expense_data.expense_date > date.today():
            raise ValidationError("Expense date cannot be in the future")
        
        # Check if budget exists and is active
        budget = None
        if expense_data.budget_id:
            budget_result = await self.db.execute(
                select(Budget).where(
                    and_(
                        Budget.id == expense_data.budget_id,
                        Budget.student_id == expense_data.student_id,
                        Budget.status == "active"
                    )
                )
            )
            budget = budget_result.scalar_one_or_none()
            
            if not budget:
                raise ValidationError("Invalid or inactive budget")
            
            # Check if expense date is within budget period
            if not (budget.start_date <= expense_data.expense_date <= budget.end_date):
                raise ValidationError("Expense date outside budget period")
        
        # Create expense
        expense = Expense(
            user_id=expense_data.user_id,
            student_id=expense_data.student_id,
            budget_id=expense_data.budget_id,
            title=expense_data.title,
            description=expense_data.description,
            category=expense_data.category,
            amount=expense_data.amount,
            currency=expense_data.currency,
            payment_method=expense_data.payment_method,
            payment_reference=expense_data.payment_reference,
            is_recurring=expense_data.is_recurring,
            recurrence_frequency=expense_data.recurrence_frequency,
            expense_date=expense_data.expense_date,
            location=expense_data.location,
            city=expense_data.city,
            tags=expense_data.tags,
        )
        
        self.db.add(expense)
        await self.db.commit()
        await self.db.refresh(expense)
        
        # Update budget spending if applicable
        if budget:
            budget.spent_amount += expense_data.amount
            budget.remaining_amount = budget.total_amount - budget.spent_amount
            await self.db.commit()
        
        logger.info(f"Created expense: {expense.title} - ₹{expense.amount}")
        return expense
    
    async def get_expense_by_id(self, expense_id: uuid.UUID) -> Optional[Expense]:
        """Get expense by ID"""
        result = await self.db.execute(
            select(Expense).where(Expense.id == expense_id)
        )
        return result.scalar_one_or_none()
    
    async def get_student_expenses(
        self,
        student_id: uuid.UUID,
        filters: Optional[ExpenseFilter] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Expense]:
        """Get expenses for a student with optional filters"""
        query = select(Expense).where(Expense.student_id == student_id)
        
        if filters:
            if filters.start_date:
                query = query.where(Expense.expense_date >= filters.start_date)
            if filters.end_date:
                query = query.where(Expense.expense_date <= filters.end_date)
            if filters.category:
                query = query.where(Expense.category == filters.category)
            if filters.min_amount:
                query = query.where(Expense.amount >= filters.min_amount)
            if filters.max_amount:
                query = query.where(Expense.amount <= filters.max_amount)
            if filters.payment_method:
                query = query.where(Expense.payment_method == filters.payment_method)
            if filters.tags:
                # Filter by tags (JSONB contains)
                for tag in filters.tags:
                    query = query.where(Expense.tags.contains([tag]))
        
        query = query.order_by(desc(Expense.expense_date), desc(Expense.created_at))
        query = query.offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_expense(
        self,
        expense_id: uuid.UUID,
        update_data: ExpenseUpdate
    ) -> Expense:
        """Update expense information"""
        expense = await self.get_expense_by_id(expense_id)
        if not expense:
            raise NotFoundError("Expense")
        
        # Store old amount for budget update
        old_amount = expense.amount
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(expense, field, value)
        
        await self.db.commit()
        await self.db.refresh(expense)
        
        # Update budget if amount changed and expense has a budget
        if expense.budget_id and update_data.amount is not None:
            new_amount = update_data.amount
            amount_diff = new_amount - old_amount
            
            budget_result = await self.db.execute(
                select(Budget).where(Budget.id == expense.budget_id)
            )
            budget = budget_result.scalar_one_or_none()
            
            if budget:
                budget.spent_amount += amount_diff
                budget.remaining_amount = budget.total_amount - budget.spent_amount
                await self.db.commit()
        
        logger.info(f"Updated expense: {expense.title}")
        return expense
    
    async def delete_expense(self, expense_id: uuid.UUID) -> bool:
        """Delete an expense"""
        expense = await self.get_expense_by_id(expense_id)
        if not expense:
            raise NotFoundError("Expense")
        
        # Store amount for budget update
        amount = expense.amount
        budget_id = expense.budget_id
        
        # Delete expense
        await self.db.delete(expense)
        await self.db.commit()
        
        # Update budget if applicable
        if budget_id:
            budget_result = await self.db.execute(
                select(Budget).where(Budget.id == budget_id)
            )
            budget = budget_result.scalar_one_or_none()
            
            if budget:
                budget.spent_amount -= amount
                budget.remaining_amount = budget.total_amount - budget.spent_amount
                await self.db.commit()
        
        logger.info(f"Deleted expense: {expense.title}")
        return True
    
    async def get_expense_summary(
        self,
        student_id: uuid.UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> ExpenseSummary:
        """Get expense summary and analytics"""
        if not start_date:
            start_date = date.today().replace(day=1)  # Start of current month
        if not end_date:
            end_date = date.today()
        
        # Total expenses
        total_result = await self.db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                and_(
                    Expense.student_id == student_id,
                    Expense.expense_date >= start_date,
                    Expense.expense_date <= end_date
                )
            )
        )
        total_expenses = float(total_result.scalar() or 0)
        
        # Category breakdown
        category_result = await self.db.execute(
            select(
                Expense.category,
                func.coalesce(func.sum(Expense.amount), 0).label("category_total")
            ).where(
                and_(
                    Expense.student_id == student_id,
                    Expense.expense_date >= start_date,
                    Expense.expense_date <= end_date
                )
            ).group_by(Expense.category)
            .order_by(desc("category_total"))
        )
        
        category_breakdown = {}
        for row in category_result:
            category_breakdown[row[0].value] = float(row[1])
        
        # Calculate daily average
        days = (end_date - start_date).days + 1
        daily_average = total_expenses / days if days > 0 else 0
        
        # Highest and lowest expenses
        extreme_result = await self.db.execute(
            select(
                func.max(Expense.amount).label("max_amount"),
                func.min(Expense.amount).label("min_amount"),
                func.count(Expense.id).label("count")
            ).where(
                and_(
                    Expense.student_id == student_id,
                    Expense.expense_date >= start_date,
                    Expense.expense_date <= end_date
                )
            )
        )
        
        row = extreme_result.first()
        highest_expense = float(row[0] or 0)
        lowest_expense = float(row[1] or 0)
        expense_count = row[2] or 0
        
        # Calculate monthly total (approximate)
        monthly_total = daily_average * 30
        
        return ExpenseSummary(
            total_expenses=total_expenses,
            category_breakdown=category_breakdown,
            daily_average=daily_average,
            monthly_total=monthly_total,
            highest_expense=highest_expense,
            lowest_expense=lowest_expense,
            expense_count=expense_count
        )
    
    async def get_spending_trend(
        self,
        student_id: uuid.UUID,
        period_days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get spending trend over time"""
        end_date = date.today()
        start_date = end_date - timedelta(days=period_days)
        
        result = await self.db.execute(
            select(
                Expense.expense_date,
                func.coalesce(func.sum(Expense.amount), 0).label("daily_total")
            ).where(
                and_(
                    Expense.student_id == student_id,
                    Expense.expense_date >= start_date,
                    Expense.expense_date <= end_date
                )
            ).group_by(Expense.expense_date)
            .order_by(Expense.expense_date)
        )
        
        trend = []
        for row in result:
            trend.append({
                "date": row[0],
                "amount": float(row[1]),
                "category": "total"
            })
        
        return trend
    
    async def get_category_insights(
        self,
        student_id: uuid.UUID,
        days: int = 90
    ) -> Dict[str, Any]:
        """Get insights about spending categories"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        # Get category averages
        result = await self.db.execute(
            select(
                Expense.category,
                func.avg(Expense.amount).label("avg_amount"),
                func.count(Expense.id).label("count"),
                func.sum(Expense.amount).label("total_amount")
            ).where(
                and_(
                    Expense.student_id == student_id,
                    Expense.expense_date >= start_date,
                    Expense.expense_date <= end_date
                )
            ).group_by(Expense.category)
            .order_by(desc("total_amount"))
        )
        
        insights = {
            "categories": [],
            "total_spent": 0,
            "most_frequent_category": None,
            "most_expensive_category": None
        }
        
        max_count = 0
        max_total = 0
        
        for row in result:
            category_data = {
                "category": row[0].value,
                "average_amount": float(row[1] or 0),
                "transaction_count": row[2] or 0,
                "total_amount": float(row[3] or 0)
            }
            insights["categories"].append(category_data)
            insights["total_spent"] += category_data["total_amount"]
            
            if category_data["transaction_count"] > max_count:
                max_count = category_data["transaction_count"]
                insights["most_frequent_category"] = category_data["category"]
            
            if category_data["total_amount"] > max_total:
                max_total = category_data["total_amount"]
                insights["most_expensive_category"] = category_data["category"]
        
        return insights