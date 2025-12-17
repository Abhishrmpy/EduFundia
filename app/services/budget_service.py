from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, update
from sqlalchemy.orm import selectinload
import uuid
import logging

from ..models.budget import Budget, BudgetStatus, BudgetPeriod
from ..models.expense import Expense
from ..models.student import Student
from ..schemas.budget import BudgetCreate, BudgetUpdate, BudgetAnalytics, BudgetRecommendation
from ..core.exceptions import NotFoundError, ValidationError, ConflictError
from ..integrations.vertex_ai import vertex_ai_client

logger = logging.getLogger(__name__)


class BudgetService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_budget(self, budget_data: BudgetCreate) -> Budget:
        """Create a new budget"""
        # Validate dates
        if budget_data.end_date <= budget_data.start_date:
            raise ValidationError("End date must be after start date")
        
        # Check for overlapping budgets
        overlapping = await self.db.execute(
            select(Budget).where(
                and_(
                    Budget.student_id == budget_data.student_id,
                    Budget.status == BudgetStatus.ACTIVE,
                    or_(
                        and_(
                            Budget.start_date <= budget_data.end_date,
                            Budget.end_date >= budget_data.start_date
                        ),
                        Budget.period == BudgetPeriod.CUSTOM
                    )
                )
            )
        )
        
        if overlapping.scalar_one_or_none():
            raise ConflictError("Active budget already exists for this period")
        
        # Calculate remaining amount (initially same as total)
        remaining = budget_data.total_amount
        
        # Create budget
        budget = Budget(
            user_id=budget_data.user_id,
            student_id=budget_data.student_id,
            name=budget_data.name,
            description=budget_data.description,
            total_amount=budget_data.total_amount,
            spent_amount=0.0,
            remaining_amount=remaining,
            categories=budget_data.categories,
            period=budget_data.period,
            start_date=budget_data.start_date,
            end_date=budget_data.end_date,
            alert_threshold=budget_data.alert_threshold,
            ai_generated=budget_data.ai_generated,
            status=BudgetStatus.ACTIVE,
        )
        
        self.db.add(budget)
        await self.db.commit()
        await self.db.refresh(budget)
        
        logger.info(f"Created budget: {budget.name} for student {budget.student_id}")
        return budget
    
    async def get_budget_by_id(self, budget_id: uuid.UUID) -> Optional[Budget]:
        """Get budget by ID"""
        result = await self.db.execute(
            select(Budget).where(Budget.id == budget_id)
        )
        return result.scalar_one_or_none()
    
    async def get_student_budgets(
        self,
        student_id: uuid.UUID,
        status: Optional[BudgetStatus] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> List[Budget]:
        """Get all budgets for a student"""
        query = select(Budget).where(Budget.student_id == student_id)
        
        if status:
            query = query.where(Budget.status == status)
        
        if date_from:
            query = query.where(Budget.start_date >= date_from)
        
        if date_to:
            query = query.where(Budget.end_date <= date_to)
        
        query = query.order_by(Budget.start_date.desc())
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_budget(
        self,
        budget_id: uuid.UUID,
        update_data: BudgetUpdate
    ) -> Budget:
        """Update budget information"""
        budget = await self.get_budget_by_id(budget_id)
        if not budget:
            raise NotFoundError("Budget")
        
        # Update fields
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(budget, field, value)
        
        await self.db.commit()
        await self.db.refresh(budget)
        
        logger.info(f"Updated budget: {budget.name}")
        return budget
    
    async def delete_budget(self, budget_id: uuid.UUID) -> bool:
        """Soft delete a budget (mark as cancelled)"""
        budget = await self.get_budget_by_id(budget_id)
        if not budget:
            raise NotFoundError("Budget")
        
        budget.status = BudgetStatus.CANCELLED
        await self.db.commit()
        
        logger.info(f"Cancelled budget: {budget.name}")
        return True
    
    async def update_budget_spending(self, budget_id: uuid.UUID) -> Budget:
        """Update budget spending from expenses"""
        budget = await self.get_budget_by_id(budget_id)
        if not budget:
            raise NotFoundError("Budget")
        
        # Calculate total spent from expenses
        result = await self.db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                and_(
                    Expense.budget_id == budget_id,
                    Expense.expense_date >= budget.start_date,
                    Expense.expense_date <= budget.end_date
                )
            )
        )
        total_spent = result.scalar() or 0.0
        
        # Update budget
        budget.spent_amount = float(total_spent)
        budget.remaining_amount = budget.total_amount - budget.spent_amount
        
        # Update status based on spending
        if budget.spent_amount >= budget.total_amount:
            budget.status = BudgetStatus.EXCEEDED
        elif budget.end_date < date.today():
            budget.status = BudgetStatus.COMPLETED
        
        await self.db.commit()
        await self.db.refresh(budget)
        
        return budget
    
    async def check_budget_alerts(self, budget_id: uuid.UUID) -> List[Dict[str, Any]]:
        """Check if budget needs alerts and return alerts"""
        budget = await self.get_budget_by_id(budget_id)
        if not budget or budget.status != BudgetStatus.ACTIVE:
            return []
        
        alerts = []
        utilization = budget.spent_amount / budget.total_amount
        
        # Check threshold alert
        if utilization >= budget.alert_threshold:
            if not budget.last_alert_sent_at or (
                datetime.utcnow() - budget.last_alert_sent_at > timedelta(hours=24)
            ):
                alerts.append({
                    "type": "budget_threshold",
                    "message": f"Budget '{budget.name}' is {utilization:.0%} spent",
                    "priority": "high" if utilization >= 0.9 else "medium"
                })
                budget.last_alert_sent_at = datetime.utcnow()
        
        # Check daily spending rate
        days_passed = (date.today() - budget.start_date).days + 1
        total_days = (budget.end_date - budget.start_date).days + 1
        expected_spending = (budget.total_amount / total_days) * days_passed
        
        if budget.spent_amount > expected_spending * 1.2:  # 20% over expected
            alerts.append({
                "type": "spending_rate",
                "message": "You're spending faster than planned",
                "priority": "medium"
            })
        
        if alerts:
            await self.db.commit()
        
        return alerts
    
    async def get_budget_analytics(self, budget_id: uuid.UUID) -> BudgetAnalytics:
        """Get detailed analytics for a budget"""
        budget = await self.get_budget_by_id(budget_id)
        if not budget:
            raise NotFoundError("Budget")
        
        # Get category spending
        result = await self.db.execute(
            select(
                Expense.category,
                func.coalesce(func.sum(Expense.amount), 0).label("total_spent")
            ).where(
                and_(
                    Expense.budget_id == budget_id,
                    Expense.expense_date >= budget.start_date,
                    Expense.expense_date <= budget.end_date
                )
            ).group_by(Expense.category)
        )
        
        category_spending = {}
        category_utilization = {}
        
        for row in result:
            category = row[0].value
            spent = float(row[1])
            category_spending[category] = spent
            
            # Calculate utilization for this category
            budget_for_category = budget.categories.get(category, 0)
            if budget_for_category > 0:
                utilization = spent / budget_for_category
                category_utilization[category] = utilization
        
        # Get daily spending trend
        daily_result = await self.db.execute(
            select(
                Expense.expense_date,
                func.coalesce(func.sum(Expense.amount), 0).label("daily_spent")
            ).where(
                and_(
                    Expense.budget_id == budget_id,
                    Expense.expense_date >= budget.start_date,
                    Expense.expense_date <= budget.end_date
                )
            ).group_by(Expense.expense_date)
            .order_by(Expense.expense_date)
        )
        
        daily_trend = []
        for row in daily_result:
            daily_trend.append({
                "date": row[0],
                "amount": float(row[1])
            })
        
        # Calculate projected end balance
        days_passed = (date.today() - budget.start_date).days + 1
        total_days = (budget.end_date - budget.start_date).days + 1
        daily_spending_rate = budget.spent_amount / days_passed if days_passed > 0 else 0
        projected_total = daily_spending_rate * total_days
        projected_balance = budget.total_amount - projected_total
        
        # Generate recommendations
        recommendations = []
        if budget.spent_amount > budget.total_amount * 0.8:
            recommendations.append("Consider reducing discretionary spending")
        
        # Check category overspending
        for category, spent in category_spending.items():
            budget_amount = budget.categories.get(category, 0)
            if budget_amount > 0 and spent > budget_amount * 1.1:
                recommendations.append(f"Reduce spending in {category}")
        
        # Check for alerts
        alerts = await self.check_budget_alerts(budget_id)
        
        return BudgetAnalytics(
            budget=budget,
            category_spending=category_spending,
            category_utilization=category_utilization,
            daily_spending_trend=daily_trend,
            projected_end_balance=projected_balance,
            recommendations=recommendations,
            alerts=[alert["message"] for alert in alerts]
        )
    
    async def generate_ai_budget_recommendation(
        self,
        student_id: uuid.UUID
    ) -> BudgetRecommendation:
        """Generate AI-powered budget recommendation"""
        # Get student data
        result = await self.db.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()
        
        if not student:
            raise NotFoundError("Student")
        
        # Get recent expenses (last 3 months)
        three_months_ago = date.today() - timedelta(days=90)
        expenses_result = await self.db.execute(
            select(Expense).where(
                and_(
                    Expense.student_id == student_id,
                    Expense.expense_date >= three_months_ago
                )
            ).order_by(Expense.expense_date.desc())
        )
        expenses = list(expenses_result.scalars().all())
        
        # Get historical budgets
        budgets_result = await self.db.execute(
            select(Budget).where(
                and_(
                    Budget.student_id == student_id,
                    Budget.status.in_([BudgetStatus.COMPLETED, BudgetStatus.EXCEEDED])
                )
            ).order_by(Budget.end_date.desc())
            .limit(5)
        )
        historical_budgets = list(budgets_result.scalars().all())
        
        # Convert to dictionaries for AI
        historical_data = []
        for budget in historical_budgets:
            historical_data.append({
                "total_amount": float(budget.total_amount),
                "spent_amount": float(budget.spent_amount),
                "categories": budget.categories,
                "period": budget.period.value,
                "start_date": budget.start_date.isoformat(),
                "end_date": budget.end_date.isoformat(),
                "utilization": float(budget.spent_amount / budget.total_amount) if budget.total_amount > 0 else 0
            })
        
        # Call AI service
        ai_recommendation = await vertex_ai_client.generate_budget_recommendation(
            student=student,
            expenses=expenses,
            historical_budgets=historical_data
        )
        
        return BudgetRecommendation(
            total_amount=ai_recommendation["total_monthly_budget"],
            categories={
                category: data["amount"]
                for category, data in ai_recommendation["categories"].items()
            },
            confidence_score=ai_recommendation.get("ai_confidence_score", 0.8),
            rationale="AI-generated based on spending patterns and financial situation",
            recommendations=ai_recommendation.get("key_recommendations", []),
            warnings=ai_recommendation.get("risk_warnings", [])
        )