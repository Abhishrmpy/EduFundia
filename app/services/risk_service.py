from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import selectinload
import uuid
import logging
import asyncio

from ..models.student import Student
from ..models.expense import Expense
from ..models.budget import Budget, BudgetStatus
from ..models.scholarship import ScholarshipApplication, ApplicationStatus
from ..schemas.student import RiskAssessment
from ..core.exceptions import NotFoundError
from ..integrations.vertex_ai import vertex_ai_client

logger = logging.getLogger(__name__)


class RiskService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def calculate_financial_stress_score(
        self,
        student_id: uuid.UUID
    ) -> float:
        """Calculate financial stress score (0-100)"""
        # Get student data
        student_result = await self.db.execute(
            select(Student).where(Student.id == student_id)
        )
        student = student_result.scalar_one_or_none()
        
        if not student:
            raise NotFoundError("Student")
        
        # Get recent expenses (last 30 days)
        thirty_days_ago = datetime.utcnow().date() - timedelta(days=30)
        expense_result = await self.db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                and_(
                    Expense.student_id == student_id,
                    Expense.expense_date >= thirty_days_ago
                )
            )
        )
        monthly_expenses = float(expense_result.scalar() or 0)
        
        # Calculate income (monthly allowance or estimate from annual income)
        monthly_income = student.monthly_allowance or (student.family_annual_income / 12)
        
        # Factor 1: Expense-to-Income Ratio (40% weight)
        if monthly_income > 0:
            expense_ratio = monthly_expenses / monthly_income
            expense_score = min(expense_ratio * 100, 100)  # Cap at 100
        else:
            expense_score = 100  # No income = maximum stress
        
        # Factor 2: Debt Burden (25% weight)
        debt_score = 0
        if student.has_education_loan and student.education_loan_amount:
            # Debt-to-income ratio
            if student.family_annual_income > 0:
                debt_ratio = student.education_loan_amount / student.family_annual_income
                debt_score = min(debt_ratio * 200, 100)  # Cap at 100
        
        # Factor 3: Savings Buffer (20% weight)
        # Check if student has any savings or emergency fund
        # For now, we'll use a simple heuristic
        savings_score = 0
        if monthly_income > 0:
            # If expenses are less than 80% of income, assume some savings
            if monthly_expenses < monthly_income * 0.8:
                savings_score = 20  # Some buffer
            elif monthly_expenses >= monthly_income:
                savings_score = 100  # No savings, spending all income
        
        # Factor 4: Budget Compliance (15% weight)
        budget_score = await self._calculate_budget_compliance_score(student_id)
        
        # Weighted average
        stress_score = (
            expense_score * 0.40 +
            debt_score * 0.25 +
            savings_score * 0.20 +
            budget_score * 0.15
        )
        
        return min(max(stress_score, 0), 100)
    
    async def _calculate_budget_compliance_score(self, student_id: uuid.UUID) -> float:
        """Calculate how well student follows budgets"""
        # Get active budgets
        budget_result = await self.db.execute(
            select(Budget).where(
                and_(
                    Budget.student_id == student_id,
                    Budget.status == BudgetStatus.ACTIVE
                )
            )
        )
        budgets = list(budget_result.scalars().all())
        
        if not budgets:
            return 50  # Neutral score if no budgets
        
        total_utilization = 0
        budget_count = 0
        
        for budget in budgets:
            if budget.total_amount > 0:
                utilization = budget.spent_amount / budget.total_amount
                # Score based on utilization (80-90% is ideal)
                if 0.8 <= utilization <= 0.9:
                    score = 0  # Good utilization
                elif utilization > 1:
                    score = 100  # Overspent
                else:
                    # Linear score from 0-100 based on deviation from ideal
                    score = abs(utilization - 0.85) * 200  # Scale to 0-100
                
                total_utilization += min(score, 100)
                budget_count += 1
        
        return total_utilization / budget_count if budget_count > 0 else 50
    
    async def calculate_dropout_risk_score(
        self,
        student_id: uuid.UUID
    ) -> float:
        """Calculate dropout risk score (0-100)"""
        financial_stress = await self.calculate_financial_stress_score(student_id)
        
        # Get academic performance
        student_result = await self.db.execute(
            select(Student).where(Student.id == student_id)
        )
        student = student_result.scalar_one_or_none()
        
        if not student:
            raise NotFoundError("Student")
        
        # Factor 1: Financial Stress (60% weight)
        financial_factor = financial_stress * 0.6
        
        # Factor 2: Academic Performance (20% weight)
        academic_factor = 0
        if student.current_cgpa:
            if student.current_cgpa < 6.0:  # Below 6.0 CGPA
                academic_factor = 80 * 0.2
            elif student.current_cgpa < 7.0:  # 6.0-7.0 CGPA
                academic_factor = 40 * 0.2
            else:  # Above 7.0 CGPA
                academic_factor = 10 * 0.2
        else:
            academic_factor = 30 * 0.2  # Unknown performance
        
        # Factor 3: Scholarship Success (10% weight)
        scholarship_factor = await self._calculate_scholarship_success_score(student_id) * 0.1
        
        # Factor 4: Year of Study (10% weight)
        year_factor = self._calculate_year_risk_factor(student.current_year) * 0.1
        
        # Total risk score
        dropout_risk = (
            financial_factor +
            academic_factor +
            scholarship_factor +
            year_factor
        )
        
        return min(max(dropout_risk, 0), 100)
    
    async def _calculate_scholarship_success_score(self, student_id: uuid.UUID) -> float:
        """Calculate scholarship success rate"""
        # Get scholarship applications
        app_result = await self.db.execute(
            select(ScholarshipApplication).where(
                ScholarshipApplication.student_id == student_id
            )
        )
        applications = list(app_result.scalars().all())
        
        if not applications:
            return 50  # Neutral if no applications
        
        successful = 0
        total_considered = 0
        
        for app in applications:
            if app.status in [ApplicationStatus.APPROVED, ApplicationStatus.AWARDED, ApplicationStatus.DISBURSED]:
                successful += 1
                total_considered += 1
            elif app.status in [ApplicationStatus.REJECTED, ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW]:
                total_considered += 1
        
        if total_considered == 0:
            return 50
        
        success_rate = (successful / total_considered) * 100
        # Invert for risk score (low success = high risk)
        return 100 - success_rate
    
    def _calculate_year_risk_factor(self, current_year: int) -> float:
        """Calculate risk factor based on year of study"""
        # Higher risk in first and final years
        if current_year == 1:
            return 70  # First year adjustment risk
        elif current_year >= 4:  # Final year or beyond
            return 60  # Final year pressure
        else:
            return 40  # Middle years relatively stable
    
    async def get_risk_assessment(
        self,
        student_id: uuid.UUID,
        use_ai: bool = True
    ) -> RiskAssessment:
        """Get comprehensive risk assessment"""
        # Calculate base scores
        financial_stress = await self.calculate_financial_stress_score(student_id)
        dropout_risk = await self.calculate_dropout_risk_score(student_id)
        
        # Get student data for AI analysis
        student_result = await self.db.execute(
            select(Student).where(Student.id == student_id)
        )
        student = student_result.scalar_one_or_none()
        
        if not student:
            raise NotFoundError("Student")
        
        # Get recent expenses for AI
        ninety_days_ago = datetime.utcnow().date() - timedelta(days=90)
        expense_result = await self.db.execute(
            select(Expense).where(
                and_(
                    Expense.student_id == student_id,
                    Expense.expense_date >= ninety_days_ago
                )
            )
        )
        expenses = list(expense_result.scalars().all())
        
        factors = {
            "expense_to_income_ratio": await self._calculate_expense_income_ratio(student_id),
            "debt_burden": await self._calculate_debt_burden(student),
            "budget_compliance": await self._calculate_budget_compliance_score(student_id),
            "scholarship_success": await self._calculate_scholarship_success_score(student_id),
            "academic_performance": self._calculate_academic_performance_factor(student),
        }
        
        recommendations = []
        
        # Generate recommendations based on risk factors
        if financial_stress > 70:
            recommendations.append("High financial stress detected. Consider applying for emergency scholarships.")
            recommendations.append("Review and reduce discretionary spending.")
        
        if dropout_risk > 60:
            recommendations.append("Elevated dropout risk. Speak with college financial aid office.")
            recommendations.append("Explore part-time work opportunities on campus.")
        
        if factors["debt_burden"] > 50:
            recommendations.append("High debt burden. Consider loan restructuring options.")
        
        if factors["budget_compliance"] > 70:
            recommendations.append("Poor budget compliance. Set up spending alerts and track expenses daily.")
        
        # Use AI for additional insights if enabled
        if use_ai:
            try:
                ai_insights = await vertex_ai_client.calculate_financial_stress_score(
                    student=student,
                    expenses=expenses,
                    upcoming_fees=[]  # Could add fee data here
                )
                
                # Merge AI recommendations
                if "interventions" in ai_insights:
                    recommendations.extend(ai_insights["interventions"])
                
                # Update factors with AI insights
                if "key_factors" in ai_insights:
                    factors.update(ai_insights["key_factors"])
                
            except Exception as e:
                logger.error(f"AI risk analysis failed: {e}")
                # Continue with rule-based analysis
        
        # Add generic recommendations if none generated
        if not recommendations:
            if financial_stress < 30:
                recommendations.append("Financial health is good. Consider building an emergency fund.")
            else:
                recommendations.append("Monitor expenses and explore scholarship opportunities.")
        
        return RiskAssessment(
            financial_stress_score=round(financial_stress, 1),
            dropout_risk_score=round(dropout_risk, 1),
            factors=factors,
            recommendations=recommendations[:5],  # Limit to top 5
            assessment_date=datetime.utcnow()
        )
    
    async def _calculate_expense_income_ratio(self, student_id: uuid.UUID) -> float:
        """Calculate monthly expense to income ratio"""
        student_result = await self.db.execute(
            select(Student).where(Student.id == student_id)
        )
        student = student_result.scalar_one_or_none()
        
        if not student:
            return 0
        
        # Last 30 days expenses
        thirty_days_ago = datetime.utcnow().date() - timedelta(days=30)
        expense_result = await self.db.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                and_(
                    Expense.student_id == student_id,
                    Expense.expense_date >= thirty_days_ago
                )
            )
        )
        monthly_expenses = float(expense_result.scalar() or 0)
        
        monthly_income = student.monthly_allowance or (student.family_annual_income / 12)
        
        if monthly_income > 0:
            ratio = monthly_expenses / monthly_income
            return min(ratio * 100, 100)  # Convert to percentage, cap at 100
        return 100  # No income = 100% ratio
    
    async def _calculate_debt_burden(self, student: Student) -> float:
        """Calculate debt burden as percentage of annual income"""
        if student.has_education_loan and student.education_loan_amount and student.family_annual_income > 0:
            burden = (student.education_loan_amount / student.family_annual_income) * 100
            return min(burden, 100)  # Cap at 100%
        return 0
    
    def _calculate_academic_performance_factor(self, student: Student) -> float:
        """Calculate academic performance factor"""
        if student.current_cgpa:
            if student.current_cgpa >= 8.0:
                return 10  # Excellent
            elif student.current_cgpa >= 7.0:
                return 30  # Good
            elif student.current_cgpa >= 6.0:
                return 60  # Average
            else:
                return 90  # Poor
        return 50  # Unknown
    
    async def get_at_risk_students(
        self,
        threshold: float = 70.0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get list of students at risk (financial stress > threshold)"""
        # Get all active students
        students_result = await self.db.execute(
            select(Student).where(Student.is_active == True)
        )
        students = list(students_result.scalars().all())
        
        at_risk_students = []
        
        # Calculate risk for each student (could be optimized with batch processing)
        for student in students[:limit]:  # Limit for performance
            try:
                stress_score = await self.calculate_financial_stress_score(student.id)
                
                if stress_score >= threshold:
                    dropout_score = await self.calculate_dropout_risk_score(student.id)
                    
                    at_risk_students.append({
                        "student_id": student.id,
                        "enrollment_number": student.enrollment_number,
                        "full_name": student.user.full_name,
                        "email": student.user.email,
                        "college": student.college_name,
                        "course": student.course_name,
                        "financial_stress_score": round(stress_score, 1),
                        "dropout_risk_score": round(dropout_score, 1),
                        "family_income": student.family_annual_income,
                        "has_education_loan": student.has_education_loan,
                        "last_updated": datetime.utcnow()
                    })
            except Exception as e:
                logger.error(f"Error calculating risk for student {student.id}: {e}")
                continue
        
        # Sort by risk score
        at_risk_students.sort(key=lambda x: x["financial_stress_score"], reverse=True)
        
        return at_risk_students
    
    async def update_student_risk_scores(self, student_id: uuid.UUID) -> Student:
        """Update risk scores in student record"""
        student_result = await self.db.execute(
            select(Student).where(Student.id == student_id)
        )
        student = student_result.scalar_one_or_none()
        
        if not student:
            raise NotFoundError("Student")
        
        # Calculate scores
        financial_stress = await self.calculate_financial_stress_score(student_id)
        dropout_risk = await self.calculate_dropout_risk_score(student_id)
        
        # Update student record
        student.financial_stress_score = financial_stress
        student.dropout_risk_score = dropout_risk
        student.last_risk_calculated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(student)
        
        logger.info(f"Updated risk scores for student {student.enrollment_number}: "
                   f"Stress={financial_stress:.1f}, Dropout={dropout_risk:.1f}")
        
        return student