import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import asyncio
from google.cloud import aiplatform
from google.oauth2 import service_account
from .config import settings
from ..models.student import Student
from ..models.expense import Expense
from ..schemas.budget import BudgetCreate

logger = logging.getLogger(__name__)


class VertexAIClient:
    def __init__(self):
        self.project = settings.google_cloud_project
        self.location = settings.vertex_ai_location
        self.model_name = settings.vertex_ai_model
        
        # Initialize Vertex AI
        try:
            aiplatform.init(
                project=self.project,
                location=self.location,
            )
            logger.info(f"Vertex AI initialized for project {self.project}")
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {e}")
            raise
    
    async def generate_budget_recommendation(
        self,
        student: Student,
        expenses: List[Expense],
        historical_budgets: List[Dict]
    ) -> Dict[str, Any]:
        """Generate AI-powered budget recommendations"""
        
        prompt = self._build_budget_prompt(student, expenses, historical_budgets)
        
        try:
            # Call Vertex AI Gemini API
            model = aiplatform.GenerativeModel(self.model_name)
            
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config={
                    "temperature": 0.2,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 2048,
                }
            )
            
            if not response.text:
                raise ValueError("Empty response from AI model")
            
            # Parse AI response
            budget_data = self._parse_budget_response(response.text)
            
            # Validate and enhance with domain logic
            validated_budget = self._validate_budget_recommendation(
                budget_data, student, expenses
            )
            
            logger.info(f"Generated budget recommendation for student {student.id}")
            return validated_budget
            
        except Exception as e:
            logger.error(f"AI budget generation failed: {e}")
            # Fallback to rule-based budgeting
            return self._generate_fallback_budget(student, expenses)
    
    def _build_budget_prompt(
        self,
        student: Student,
        expenses: List[Expense],
        historical_budgets: List[Dict]
    ) -> str:
        """Build comprehensive prompt for budget generation"""
        
        # Analyze spending patterns
        expense_summary = self._summarize_expenses(expenses)
        
        prompt = f"""
        You are a financial advisor for college students in India. Generate a personalized monthly budget.
        
        STUDENT PROFILE:
        - Course: {student.course} ({student.year_of_study} year)
        - Location: {student.current_city}, {student.home_state}
        - Family Income: ₹{student.family_annual_income:,.0f}/year
        - Monthly Allowance: ₹{student.monthly_allowance or 0}/month
        - Has Education Loan: {student.has_education_loan}
        
        CURRENT SPENDING (Last 3 months):
        {expense_summary}
        
        HISTORICAL BUDGET PERFORMANCE:
        {json.dumps(historical_budgets, indent=2) if historical_budgets else "No historical data"}
        
        GENERATE A BUDGET WITH THESE CATEGORIES:
        1. Tuition & Academic Fees
        2. Accommodation & Hostel
        3. Food & Groceries
        4. Transportation
        5. Books & Study Materials
        6. Medical & Healthcare
        7. Personal & Entertainment
        8. Savings & Emergency Fund
        
        CONSIDER THESE LOCAL FACTORS:
        - City cost of living: {self._get_city_cost_index(student.current_city)}
        - Student discounts availability
        - Seasonal variations (exam periods, festivals)
        
        OUTPUT FORMAT (JSON):
        {{
            "total_monthly_budget": number,
            "categories": {{
                "tuition": {{"amount": number, "percentage": number, "rationale": "string"}},
                "hostel": {{"amount": number, "percentage": number, "rationale": "string"}},
                "food": {{"amount": number, "percentage": number, "rationale": "string"}},
                "transport": {{"amount": number, "percentage": number, "rationale": "string"}},
                "books": {{"amount": number, "percentage": number, "rationale": "string"}},
                "medical": {{"amount": number, "percentage": number, "rationale": "string"}},
                "entertainment": {{"amount": number, "percentage": number, "rationale": "string"}},
                "savings": {{"amount": number, "percentage": number, "rationale": "string"}}
            }},
            "ai_confidence_score": number (0-1),
            "key_recommendations": ["string"],
            "risk_warnings": ["string"]
        }}
        
        Ensure the total is realistic for the student's financial situation.
        """
        
        return prompt
    
    def _summarize_expenses(self, expenses: List[Expense]) -> str:
        """Summarize expenses for AI prompt"""
        if not expenses:
            return "No expense data available"
        
        summary = {}
        for expense in expenses:
            category = expense.category.value
            if category not in summary:
                summary[category] = 0
            summary[category] += float(expense.amount)
        
        return "\n".join([f"- {cat}: ₹{amt:,.2f}" for cat, amt in summary.items()])
    
    def _get_city_cost_index(self, city: str) -> float:
        """Get cost of living index for Indian cities"""
        # This could be expanded with actual data
        city_costs = {
            "mumbai": 1.5, "delhi": 1.3, "bangalore": 1.4,
            "chennai": 1.2, "hyderabad": 1.1, "pune": 1.2,
            "kolkata": 1.0, "ahmedabad": 0.9
        }
        return city_costs.get(city.lower(), 1.0)
    
    def _parse_budget_response(self, response_text: str) -> Dict:
        """Parse and validate AI response"""
        try:
            # Extract JSON from response
            lines = response_text.strip().split('\n')
            json_start = None
            json_end = None
            
            for i, line in enumerate(lines):
                if line.strip().startswith('{'):
                    json_start = i
                if line.strip().endswith('}'):
                    json_end = i
                    break
            
            if json_start is not None and json_end is not None:
                json_str = '\n'.join(lines[json_start:json_end + 1])
                return json.loads(json_str)
            else:
                # Try to find JSON in the entire text
                import re
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                else:
                    raise ValueError("No JSON found in response")
                    
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse AI response: {e}")
            raise
    
    def _validate_budget_recommendation(
        self,
        budget_data: Dict,
        student: Student,
        expenses: List[Expense]
    ) -> Dict:
        """Validate and adjust AI recommendations with business logic"""
        
        total = budget_data.get("total_monthly_budget", 0)
        
        # Cap budget based on student's financial capacity
        max_reasonable = float(student.monthly_allowance or 0) * 1.2  # 20% buffer
        if total > max_reasonable and max_reasonable > 0:
            scaling_factor = max_reasonable / total
            for category in budget_data["categories"].values():
                category["amount"] *= scaling_factor
                category["percentage"] = (category["amount"] / max_reasonable) * 100
            budget_data["total_monthly_budget"] = max_reasonable
            budget_data["risk_warnings"].append(
                "Budget capped to 120% of monthly allowance for sustainability"
            )
        
        # Ensure minimum allocation for essentials
        essentials = ["tuition", "hostel", "food"]
        for essential in essentials:
            if essential in budget_data["categories"]:
                current_pct = budget_data["categories"][essential]["percentage"]
                if current_pct < 10:  # Minimum 10% for essentials
                    budget_data["categories"][essential]["percentage"] = 10
                    budget_data["categories"][essential]["amount"] = total * 0.1
                    budget_data["categories"][essential]["rationale"] += " (Adjusted to minimum)"
        
        # Recalculate percentages
        total_amount = sum(cat["amount"] for cat in budget_data["categories"].values())
        for category in budget_data["categories"].values():
            category["percentage"] = (category["amount"] / total_amount) * 100
        
        return budget_data
    
    def _generate_fallback_budget(
        self,
        student: Student,
        expenses: List[Expense]
    ) -> Dict:
        """Rule-based fallback budget generation"""
        
        # Base budget on monthly allowance or average Indian student spending
        base_amount = float(student.monthly_allowance or 10000)
        
        # Adjust for city cost
        city_factor = self._get_city_cost_index(student.current_city)
        adjusted_amount = base_amount * city_factor
        
        # Standard allocation percentages (based on Indian student spending patterns)
        allocations = {
            "tuition": {"percentage": 40, "rationale": "Academic fees and college expenses"},
            "hostel": {"percentage": 25, "rationale": "Accommodation and utilities"},
            "food": {"percentage": 20, "rationale": "Food and groceries"},
            "transport": {"percentage": 5, "rationale": "Local transportation"},
            "books": {"percentage": 5, "rationale": "Study materials and books"},
            "medical": {"percentage": 2, "rationale": "Healthcare and insurance"},
            "entertainment": {"percentage": 2, "rationale": "Recreation and social activities"},
            "savings": {"percentage": 1, "rationale": "Emergency fund and savings"}
        }
        
        categories = {}
        for name, alloc in allocations.items():
            amount = adjusted_amount * (alloc["percentage"] / 100)
            categories[name] = {
                "amount": round(amount, 2),
                "percentage": alloc["percentage"],
                "rationale": alloc["rationale"]
            }
        
        return {
            "total_monthly_budget": round(adjusted_amount, 2),
            "categories": categories,
            "ai_confidence_score": 0.7,  # Lower confidence for rule-based
            "key_recommendations": [
                "Consider applying for scholarships to reduce financial burden",
                "Track expenses weekly to stay within budget",
                "Look for student discounts on transportation and entertainment"
            ],
            "risk_warnings": [
                "Based on rule-based allocation due to AI service limitation",
                "Adjust percentages based on actual spending patterns"
            ]
        }
    
    async def calculate_financial_stress_score(
        self,
        student: Student,
        expenses: List[Expense],
        upcoming_fees: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate financial stress and dropout risk scores"""
        
        prompt = f"""
        Calculate financial stress score (0-1) and dropout risk score (0-1) for a student.
        
        STUDENT DATA:
        - Course: {student.course}
        - Year: {student.year_of_study}
        - Family Income: ₹{student.family_annual_income}/year
        - Monthly Expenses: ₹{sum(e.amount for e in expenses if e.transaction_type.value == 'expense')}/month
        - Upcoming Fees: {json.dumps(upcoming_fees)}
        - Has Loan: {student.has_education_loan}
        - Loan Amount: {student.loan_amount or 0}
        
        CONSIDER THESE FACTORS:
        1. Income-to-expense ratio
        2. Debt burden
        3. Course completion timeline
        4. Available scholarships
        5. Emergency fund availability
        6. Family support system
        7. Part-time work possibilities
        
        OUTPUT FORMAT (JSON):
        {{
            "financial_stress_score": number (0-1),
            "dropout_risk_score": number (0-1),
            "key_factors": {{
                "income_expense_ratio": number,
                "debt_burden": number,
                "fee_pressure": number,
                "support_system": number
            }},
            "interventions": ["string"],
            "confidence_level": number
        }}
        """
        
        try:
            model = aiplatform.GenerativeModel(self.model_name)
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config={"max_output_tokens": 1024}
            )
            
            return json.loads(response.text)
            
        except Exception as e:
            logger.error(f"Stress score calculation failed: {e}")
            return self._calculate_fallback_stress_score(student, expenses, upcoming_fees)
    
    def _calculate_fallback_stress_score(
        self,
        student: Student,
        expenses: List[Expense],
        upcoming_fees: List[Dict]
    ) -> Dict:
        """Fallback rule-based stress scoring"""
        
        monthly_expenses = sum(e.amount for e in expenses if e.transaction_type.value == 'expense')
        monthly_income = float(student.monthly_allowance or 0)
        
        # Calculate income-to-expense ratio
        if monthly_income > 0:
            expense_ratio = monthly_expenses / monthly_income
        else:
            expense_ratio = 2.0  # High stress if no income
        
        # Debt burden factor
        debt_burden = 0
        if student.has_education_loan and student.loan_amount:
            debt_burden = min(student.loan_amount / (student.family_annual_income or 1), 1)
        
        # Fee pressure
        total_upcoming_fees = sum(fee.get("amount", 0) for fee in upcoming_fees)
        fee_pressure = min(total_upcoming_fees / (student.family_annual_income or 1), 1)
        
        # Calculate composite scores
        financial_stress = min(0.3 * expense_ratio + 0.4 * debt_burden + 0.3 * fee_pressure, 1)
        
        # Dropout risk (higher if stress > 0.7 and in early years)
        dropout_risk = financial_stress
        if student.year_of_study in ["1st", "2nd"] and financial_stress > 0.7:
            dropout_risk = min(dropout_risk * 1.3, 1)
        
        return {
            "financial_stress_score": round(financial_stress, 3),
            "dropout_risk_score": round(dropout_risk, 3),
            "key_factors": {
                "income_expense_ratio": round(expense_ratio, 3),
                "debt_burden": round(debt_burden, 3),
                "fee_pressure": round(fee_pressure, 3),
                "support_system": 0.5  # Default
            },
            "interventions": [
                "Consider part-time work opportunities",
                "Apply for need-based scholarships",
                "Explore education loan restructuring"
            ],
            "confidence_level": 0.6
        }


# Singleton instance
vertex_ai_client = VertexAIClient()