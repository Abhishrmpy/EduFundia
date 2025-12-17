import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import asyncio
from google.cloud import aiplatform
from google.oauth2 import service_account
from ..core.config import settings
from ..models.student import Student
from ..models.expense import Expense

logger = logging.getLogger(__name__)


class VertexAIClient:
    """Vertex AI (Gemini) integration service"""
    
    def __init__(self):
        self.project = settings.google_cloud_project
        self.location = settings.vertex_ai_location
        self.model_name = settings.vertex_ai_model
        self.initialized = False
        
        self._initialize_vertex_ai()
    
    def _initialize_vertex_ai(self):
        """Initialize Vertex AI client"""
        try:
            if not self.project:
                logger.warning("Google Cloud project not configured. Vertex AI will use mock mode.")
                return
            
            # Initialize Vertex AI
            aiplatform.init(
                project=self.project,
                location=self.location,
            )
            
            self.initialized = True
            logger.info(f"Vertex AI initialized for project {self.project}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {e}")
            self.initialized = False
    
    async def generate_budget_recommendation(
        self,
        student: Student,
        expenses: List[Expense],
        historical_budgets: List[Dict]
    ) -> Dict[str, Any]:
        """Generate AI-powered budget recommendations"""
        
        # Build prompt
        prompt = self._build_budget_prompt(student, expenses, historical_budgets)
        
        try:
            if not self.initialized:
                logger.warning("Vertex AI not initialized, using rule-based budget")
                return self._generate_rule_based_budget(student, expenses)
            
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
            
            logger.info(f"Generated AI budget recommendation for student {student.id}")
            return validated_budget
            
        except Exception as e:
            logger.error(f"AI budget generation failed: {e}")
            # Fallback to rule-based budgeting
            return self._generate_rule_based_budget(student, expenses)
    
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
        - Course: {student.course_name} (Year {student.current_year} of {student.course_duration})
        - Location: {student.city}, {student.state}
        - Family Income: ₹{student.family_annual_income:,.0f}/year
        - Monthly Allowance: ₹{student.monthly_allowance or 0}/month
        - Has Education Loan: {student.has_education_loan}
        - Loan Amount: ₹{student.education_loan_amount or 0}
        
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
        - City cost of living: {self._get_city_cost_index(student.city)}
        - Student discounts availability
        - Seasonal variations (exam periods, festivals)
        
        OUTPUT FORMAT (JSON):
        {{
            "total_monthly_budget": number,
            "categories": {{
                "tuition_fee": {{"amount": number, "percentage": number, "rationale": "string"}},
                "hostel_fee": {{"amount": number, "percentage": number, "rationale": "string"}},
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
        Provide rationale for each category allocation.
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
        city_costs = {
            "mumbai": 1.5, "bombay": 1.5,
            "delhi": 1.3, "new delhi": 1.3,
            "bangalore": 1.4, "bengaluru": 1.4,
            "chennai": 1.2, "madras": 1.2,
            "hyderabad": 1.1,
            "pune": 1.2, "poona": 1.2,
            "kolkata": 1.0, "calcutta": 1.0,
            "ahmedabad": 0.9,
            "jaipur": 0.8,
            "lucknow": 0.8,
            "kanpur": 0.7,
            "nagpur": 0.8,
            "indore": 0.8,
            "thane": 1.3,
            "bhopal": 0.8,
            "visakhapatnam": 0.8,
            "patna": 0.8,
            "vadodara": 0.9,
            "ghaziabad": 1.0,
            "ludhiana": 0.8,
            "agra": 0.7,
            "nashik": 0.9,
            "faridabad": 1.0,
            "meerut": 0.8,
            "rajkot": 0.8,
            "kalyan": 1.2,
            "vasai": 1.2,
            "varanasi": 0.7,
            "srinagar": 0.8,
            "aurangabad": 0.8,
            "dhanbad": 0.7,
            "amritsar": 0.8,
            "navi mumbai": 1.4,
            "allahabad": 0.7,
            "ranchi": 0.8,
            "howrah": 0.9,
            "coimbatore": 0.9,
            "jabalpur": 0.7,
            "gwalior": 0.7,
            "vijayawada": 0.8,
            "jodhpur": 0.7,
            "madurai": 0.8,
            "raipur": 0.8,
            "kota": 0.7,
            "guwahati": 0.8,
            "chandigarh": 1.1,
            "solapur": 0.7,
            "hubli": 0.7,
            "dharwad": 0.7,
            "tirunelveli": 0.7,
            "tiruchirappalli": 0.8,
        }
        return city_costs.get(city.lower(), 1.0)
    
    def _parse_budget_response(self, response_text: str) -> Dict:
        """Parse and validate AI response"""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)
            else:
                # Try to find JSON array
                json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    data = json.loads(json_str)
                    if isinstance(data, list) and len(data) > 0:
                        return data[0]
                
                raise ValueError("No valid JSON found in response")
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse AI response: {e}")
            # Try to extract just the JSON part
            try:
                # Find text between first { and last }
                start = response_text.find('{')
                end = response_text.rfind('}') + 1
                if start != -1 and end != 0:
                    json_str = response_text[start:end]
                    return json.loads(json_str)
            except:
                pass
            
            logger.error(f"Raw response: {response_text[:500]}...")
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
        monthly_income = student.monthly_allowance or (student.family_annual_income / 12)
        max_reasonable = monthly_income * 1.2  # 20% buffer
        
        if total > max_reasonable and max_reasonable > 0:
            scaling_factor = max_reasonable / total
            for category in budget_data.get("categories", {}).values():
                if isinstance(category, dict):
                    category["amount"] = category.get("amount", 0) * scaling_factor
                    category["percentage"] = (category.get("amount", 0) / max_reasonable) * 100
            budget_data["total_monthly_budget"] = max_reasonable
            budget_data.setdefault("risk_warnings", []).append(
                "Budget capped to 120% of monthly allowance for sustainability"
            )
        
        # Ensure minimum allocation for essentials
        essentials = ["tuition_fee", "hostel_fee", "food"]
        categories = budget_data.get("categories", {})
        
        for essential in essentials:
            if essential in categories:
                category = categories[essential]
                if isinstance(category, dict):
                    current_pct = category.get("percentage", 0)
                    if current_pct < 10:  # Minimum 10% for essentials
                        category["percentage"] = 10
                        category["amount"] = total * 0.1
                        rationale = category.get("rationale", "")
                        category["rationale"] = f"{rationale} (Adjusted to minimum)"
        
        # Recalculate percentages if needed
        total_amount = sum(
            cat.get("amount", 0) for cat in categories.values() 
            if isinstance(cat, dict)
        )
        
        if total_amount > 0:
            for category in categories.values():
                if isinstance(category, dict):
                    category["percentage"] = (category.get("amount", 0) / total_amount) * 100
        
        return budget_data
    
    def _generate_rule_based_budget(
        self,
        student: Student,
        expenses: List[Expense]
    ) -> Dict:
        """Rule-based fallback budget generation"""
        
        # Base budget on monthly allowance or average Indian student spending
        monthly_income = student.monthly_allowance or (student.family_annual_income / 12)
        base_amount = monthly_income or 10000  # Default ₹10,000 if no income data
        
        # Adjust for city cost
        city_factor = self._get_city_cost_index(student.city)
        adjusted_amount = base_amount * city_factor
        
        # Standard allocation percentages for Indian students
        allocations = {
            "tuition_fee": {"percentage": 40, "rationale": "Academic fees and college expenses"},
            "hostel_fee": {"percentage": 25, "rationale": "Accommodation and utilities"},
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
            "ai_confidence_score": 0.7,
            "key_recommendations": [
                "Consider applying for scholarships to reduce financial burden",
                "Track expenses weekly to stay within budget",
                "Look for student discounts on transportation and entertainment",
                "Build an emergency fund of at least 3 months' expenses"
            ],
            "risk_warnings": [
                "Based on rule-based allocation due to AI service limitation",
                "Adjust percentages based on actual spending patterns",
                "Monitor spending closely during initial months"
            ]
        }
    
    async def calculate_financial_stress_score(
        self,
        student: Student,
        expenses: List[Expense],
        upcoming_fees: List[Dict]
    ) -> Dict[str, Any]:
        """Calculate financial stress and dropout risk using AI"""
        
        prompt = self._build_stress_analysis_prompt(student, expenses, upcoming_fees)
        
        try:
            if not self.initialized:
                logger.warning("Vertex AI not initialized, using rule-based analysis")
                return self._generate_rule_based_stress_analysis(student, expenses, upcoming_fees)
            
            model = aiplatform.GenerativeModel(self.model_name)
            response = await asyncio.to_thread(
                model.generate_content,
                prompt,
                generation_config={"max_output_tokens": 1024}
            )
            
            if not response.text:
                raise ValueError("Empty response from AI model")
            
            # Parse response
            result = self._parse_stress_response(response.text)
            return result
            
        except Exception as e:
            logger.error(f"AI stress analysis failed: {e}")
            return self._generate_rule_based_stress_analysis(student, expenses, upcoming_fees)
    
    def _build_stress_analysis_prompt(
        self,
        student: Student,
        expenses: List[Expense],
        upcoming_fees: List[Dict]
    ) -> str:
        """Build prompt for stress analysis"""
        
        expense_summary = self._summarize_expenses(expenses)
        total_upcoming_fees = sum(fee.get("amount", 0) for fee in upcoming_fees)
        
        prompt = f"""
        Analyze financial stress and dropout risk for an Indian college student.
        
        STUDENT PROFILE:
        - Course: {student.course_name} (Year {student.current_year})
        - University: {student.university_name}
        - Location: {student.city}, {student.state}
        - Family Annual Income: ₹{student.family_annual_income:,.0f}
        - Monthly Allowance: ₹{student.monthly_allowance or 0}
        - Has Education Loan: {student.has_education_loan}
        - Loan Amount: ₹{student.education_loan_amount or 0}
        - Caste Category: {student.caste_category.value}
        
        FINANCIAL SITUATION:
        - Recent Expenses (3 months): {expense_summary}
        - Upcoming Fees: ₹{total_upcoming_fees:,.0f}
        - Current CGPA: {student.current_cgpa or 'Not available'}
        
        ANALYSIS REQUEST:
        1. Calculate financial stress score (0-100, higher = more stress)
        2. Calculate dropout risk score (0-100, higher = higher risk)
        3. Identify key contributing factors
        4. Provide actionable recommendations
        
        OUTPUT FORMAT (JSON):
        {{
            "financial_stress_score": number (0-100),
            "dropout_risk_score": number (0-100),
            "key_factors": {{
                "income_expense_ratio": number (0-100),
                "debt_burden": number (0-100),
                "fee_pressure": number (0-100),
                "academic_pressure": number (0-100),
                "family_support": number (0-100)
            }},
            "interventions": ["string"],
            "confidence_level": number (0-1)
        }}
        
        Consider Indian context:
        - Cost of living in {student.city}
        - Scholarship availability for {student.caste_category.value} category
        - Part-time work opportunities for students
        - Education loan repayment pressures
        - Family expectations and support
        """
        
        return prompt
    
    def _parse_stress_response(self, response_text: str) -> Dict:
        """Parse stress analysis response"""
        try:
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except:
            pass
        
        # Default fallback
        return {
            "financial_stress_score": 50,
            "dropout_risk_score": 50,
            "key_factors": {
                "income_expense_ratio": 50,
                "debt_burden": 50,
                "fee_pressure": 50,
                "academic_pressure": 50,
                "family_support": 50
            },
            "interventions": [
                "Monitor expenses closely",
                "Explore scholarship opportunities",
                "Consider part-time work if schedule permits"
            ],
            "confidence_level": 0.6
        }
    
    def _generate_rule_based_stress_analysis(
        self,
        student: Student,
        expenses: List[Expense],
        upcoming_fees: List[Dict]
    ) -> Dict:
        """Rule-based stress analysis fallback"""
        
        # Calculate expense-to-income ratio
        monthly_income = student.monthly_allowance or (student.family_annual_income / 12)
        monthly_expenses = sum(e.amount for e in expenses) / 3  # Average over 3 months
        
        if monthly_income > 0:
            expense_ratio = monthly_expenses / monthly_income
            expense_score = min(expense_ratio * 100, 100)
        else:
            expense_score = 100
        
        # Debt burden
        debt_score = 0
        if student.has_education_loan and student.education_loan_amount:
            if student.family_annual_income > 0:
                debt_ratio = student.education_loan_amount / student.family_annual_income
                debt_score = min(debt_ratio * 200, 100)
        
        # Fee pressure
        total_fees = sum(fee.get("amount", 0) for fee in upcoming_fees)
        fee_score = 0
        if student.family_annual_income > 0:
            fee_ratio = total_fees / student.family_annual_income
            fee_score = min(fee_ratio * 100, 100)
        
        # Academic pressure
        academic_score = 0
        if student.current_cgpa:
            if student.current_cgpa < 6.0:
                academic_score = 80
            elif student.current_cgpa < 7.0:
                academic_score = 50
            else:
                academic_score = 20
        
        # Composite scores
        financial_stress = (
            expense_score * 0.4 +
            debt_score * 0.3 +
            fee_score * 0.3
        )
        
        dropout_risk = (
            financial_stress * 0.6 +
            academic_score * 0.4
        )
        
        return {
            "financial_stress_score": min(financial_stress, 100),
            "dropout_risk_score": min(dropout_risk, 100),
            "key_factors": {
                "income_expense_ratio": expense_score,
                "debt_burden": debt_score,
                "fee_pressure": fee_score,
                "academic_pressure": academic_score,
                "family_support": 50  # Default assumption
            },
            "interventions": [
                "Create a detailed budget and track expenses",
                "Apply for need-based scholarships",
                "Explore on-campus work opportunities",
                "Discuss payment plans for upcoming fees"
            ],
            "confidence_level": 0.7
        }
    
    async def match_scholarships(
        self,
        student: Student,
        available_scholarships: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Use AI to match scholarships with student profile"""
        # This would involve more complex AI matching
        # For now, return simplified version
        return []


# Singleton instance
vertex_ai_client = VertexAIClient()