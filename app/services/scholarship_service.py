from typing import Optional, List, Dict, Any
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, text
from sqlalchemy.orm import selectinload
import uuid
import logging

from ..models.scholarship import Scholarship, ScholarshipApplication, ScholarshipType, ApplicationStatus
from ..models.student import Student
from ..schemas.scholarship import ScholarshipCreate, ScholarshipUpdate, ScholarshipFilter, ScholarshipMatch
from ..core.exceptions import NotFoundError, ValidationError, ConflictError

logger = logging.getLogger(__name__)


class ScholarshipService:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_scholarship(self, scholarship_data: ScholarshipCreate) -> Scholarship:
        """Create a new scholarship (admin only)"""
        # Validate dates
        if scholarship_data.application_end_date <= scholarship_data.application_start_date:
            raise ValidationError("Application end date must be after start date")
        
        # Create scholarship
        scholarship = Scholarship(
            name=scholarship_data.name,
            description=scholarship_data.description,
            scholarship_type=scholarship_data.scholarship_type,
            provider_name=scholarship_data.provider_name,
            provider_website=str(scholarship_data.provider_website) if scholarship_data.provider_website else None,
            amount=scholarship_data.amount,
            min_amount=scholarship_data.min_amount,
            max_amount=scholarship_data.max_amount,
            is_variable=scholarship_data.is_variable,
            currency=scholarship_data.currency,
            eligibility_criteria=scholarship_data.eligibility_criteria,
            min_income=scholarship_data.min_income,
            max_income=scholarship_data.max_income,
            eligible_castes=scholarship_data.eligible_castes,
            eligible_genders=scholarship_data.eligible_genders,
            eligible_courses=scholarship_data.eligible_courses,
            eligible_states=scholarship_data.eligible_states,
            min_percentage=scholarship_data.min_percentage,
            min_cgpa=scholarship_data.min_cgpa,
            application_url=str(scholarship_data.application_url) if scholarship_data.application_url else None,
            application_fee=scholarship_data.application_fee,
            documents_required=scholarship_data.documents_required,
            application_start_date=scholarship_data.application_start_date,
            application_end_date=scholarship_data.application_end_date,
            result_date=scholarship_data.result_date,
            disbursement_date=scholarship_data.disbursement_date,
        )
        
        self.db.add(scholarship)
        await self.db.commit()
        await self.db.refresh(scholarship)
        
        logger.info(f"Created scholarship: {scholarship.name}")
        return scholarship
    
    async def get_scholarship_by_id(self, scholarship_id: uuid.UUID) -> Optional[Scholarship]:
        """Get scholarship by ID"""
        result = await self.db.execute(
            select(Scholarship).where(Scholarship.id == scholarship_id)
        )
        return result.scalar_one_or_none()
    
    async def get_all_scholarships(
        self,
        filters: Optional[ScholarshipFilter] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Scholarship]:
        """Get all scholarships with optional filters"""
        query = select(Scholarship).where(
            Scholarship.status == "active"
        )
        
        if filters:
            if filters.scholarship_type:
                query = query.where(Scholarship.scholarship_type == filters.scholarship_type)
            if filters.min_amount:
                query = query.where(or_(
                    Scholarship.amount >= filters.min_amount,
                    Scholarship.min_amount >= filters.min_amount
                ))
            if filters.max_amount:
                query = query.where(or_(
                    Scholarship.amount <= filters.max_amount,
                    Scholarship.max_amount <= filters.max_amount
                ))
            if filters.eligible_caste:
                query = query.where(Scholarship.eligible_castes.contains([filters.eligible_caste]))
            if filters.eligible_gender:
                query = query.where(Scholarship.eligible_genders.contains([filters.eligible_gender]))
            if filters.eligible_course:
                query = query.where(Scholarship.eligible_courses.contains([filters.eligible_course]))
            if filters.eligible_state:
                query = query.where(Scholarship.eligible_states.contains([filters.eligible_state]))
            if filters.application_deadline_soon:
                soon_date = date.today() + timedelta(days=7)
                query = query.where(Scholarship.application_end_date <= soon_date)
            if filters.is_featured:
                query = query.where(Scholarship.is_featured == True)
            if filters.search_query:
                search_term = f"%{filters.search_query}%"
                query = query.where(
                    or_(
                        Scholarship.name.ilike(search_term),
                        Scholarship.description.ilike(search_term),
                        Scholarship.provider_name.ilike(search_term)
                    )
                )
        
        query = query.order_by(
            desc(Scholarship.is_featured),
            desc(Scholarship.popularity_score),
            desc(Scholarship.application_end_date)
        ).offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def match_scholarships_for_student(
        self,
        student_id: uuid.UUID,
        limit: int = 20
    ) -> List[ScholarshipMatch]:
        """Find scholarships that match a student's profile"""
        # Get student profile
        result = await self.db.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()
        
        if not student:
            raise NotFoundError("Student")
        
        # Get all active scholarships
        scholarships = await self.get_all_scholarships(limit=100)
        
        matches = []
        
        for scholarship in scholarships:
            # Calculate match score
            eligibility_score = await self._calculate_eligibility_score(student, scholarship)
            match_score = await self._calculate_match_score(student, scholarship)
            
            # Only include scholarships with decent match
            if match_score >= 0.5:
                # Calculate days until deadline
                deadline_days = (scholarship.application_end_date - date.today()).days
                
                # Check if already applied
                app_result = await self.db.execute(
                    select(ScholarshipApplication).where(
                        and_(
                            ScholarshipApplication.student_id == student_id,
                            ScholarshipApplication.scholarship_id == scholarship.id
                        )
                    )
                )
                existing_app = app_result.scalar_one_or_none()
                
                application_status = "not_applied"
                if existing_app:
                    application_status = existing_app.status.value
                
                match = ScholarshipMatch(
                    scholarship=scholarship,
                    match_score=match_score,
                    eligibility_score=eligibility_score,
                    reasons=self._get_match_reasons(student, scholarship, match_score),
                    documents_needed=scholarship.documents_required or [],
                    deadline_days=deadline_days,
                    application_status=application_status
                )
                
                matches.append(match)
        
        # Sort by match score and limit results
        matches.sort(key=lambda x: x.match_score, reverse=True)
        return matches[:limit]
    
    async def _calculate_eligibility_score(
        self,
        student: Student,
        scholarship: Scholarship
    ) -> float:
        """Calculate eligibility score (0-1)"""
        score = 1.0
        reasons = []
        
        # Income check
        if scholarship.min_income and student.family_annual_income < scholarship.min_income:
            score -= 0.3
            reasons.append("Income below minimum")
        if scholarship.max_income and student.family_annual_income > scholarship.max_income:
            score -= 0.3
            reasons.append("Income above maximum")
        
        # Caste check
        if scholarship.eligible_castes and student.caste_category.value not in scholarship.eligible_castes:
            score -= 0.2
            reasons.append("Caste not eligible")
        
        # Gender check
        if scholarship.eligible_genders and student.gender.value not in scholarship.eligible_genders:
            score -= 0.1
            reasons.append("Gender not eligible")
        
        # Course check
        if scholarship.eligible_courses and student.course_name not in scholarship.eligible_courses:
            score -= 0.2
            reasons.append("Course not eligible")
        
        # State check
        if scholarship.eligible_states and student.state not in scholarship.eligible_states:
            score -= 0.1
            reasons.append("State not eligible")
        
        # Academic performance check
        if scholarship.min_percentage and student.last_semester_percentage:
            if student.last_semester_percentage < scholarship.min_percentage:
                score -= 0.3
                reasons.append("Percentage below requirement")
        
        if scholarship.min_cgpa and student.current_cgpa:
            if student.current_cgpa < scholarship.min_cgpa:
                score -= 0.3
                reasons.append("CGPA below requirement")
        
        return max(0.0, min(1.0, score))
    
    async def _calculate_match_score(
        self,
        student: Student,
        scholarship: Scholarship
    ) -> float:
        """Calculate overall match score (0-1)"""
        eligibility_score = await self._calculate_eligibility_score(student, scholarship)
        
        # Additional factors for match score
        match_factors = {
            "eligibility": eligibility_score * 0.6,
            "financial_need": self._calculate_financial_need_factor(student, scholarship) * 0.2,
            "urgency": self._calculate_urgency_factor(scholarship) * 0.1,
            "popularity": scholarship.popularity_score * 0.1
        }
        
        total_score = sum(match_factors.values())
        return min(1.0, total_score)
    
    def _calculate_financial_need_factor(
        self,
        student: Student,
        scholarship: Scholarship
    ) -> float:
        """Calculate financial need factor (0-1)"""
        # Higher need if income is low relative to scholarship amount
        if scholarship.amount and student.family_annual_income:
            ratio = scholarship.amount / student.family_annual_income
            return min(1.0, ratio * 10)  # Normalize to 0-1
        return 0.5
    
    def _calculate_urgency_factor(self, scholarship: Scholarship) -> float:
        """Calculate urgency factor based on deadline"""
        days_left = (scholarship.application_end_date - date.today()).days
        
        if days_left <= 7:
            return 1.0
        elif days_left <= 14:
            return 0.7
        elif days_left <= 30:
            return 0.4
        else:
            return 0.1
    
    def _get_match_reasons(
        self,
        student: Student,
        scholarship: Scholarship,
        match_score: float
    ) -> List[str]:
        """Get reasons for match"""
        reasons = []
        
        if match_score >= 0.8:
            reasons.append("Excellent match based on your profile")
        elif match_score >= 0.6:
            reasons.append("Good match for your profile")
        else:
            reasons.append("Partial match - check eligibility criteria")
        
        # Add specific reasons
        if scholarship.eligible_castes and student.caste_category.value in scholarship.eligible_castes:
            reasons.append(f"Eligible for {student.caste_category.value} category")
        
        if scholarship.eligible_states and student.state in scholarship.eligible_states:
            reasons.append(f"Open to students from {student.state}")
        
        if scholarship.eligible_courses and student.course_name in scholarship.eligible_courses:
            reasons.append(f"Available for {student.course_name} students")
        
        # Check deadline urgency
        days_left = (scholarship.application_end_date - date.today()).days
        if days_left <= 7:
            reasons.append(f"Application closes in {days_left} days!")
        elif days_left <= 30:
            reasons.append(f"Apply soon - {days_left} days remaining")
        
        return reasons
    
    async def create_application(
        self,
        student_id: uuid.UUID,
        scholarship_id: uuid.UUID,
        application_data: Dict[str, Any]
    ) -> ScholarshipApplication:
        """Create a scholarship application"""
        # Check if scholarship exists and is active
        scholarship = await self.get_scholarship_by_id(scholarship_id)
        if not scholarship or scholarship.status != "active":
            raise NotFoundError("Scholarship")
        
        # Check if application period is open
        today = date.today()
        if today < scholarship.application_start_date:
            raise ValidationError("Application period has not started")
        if today > scholarship.application_end_date:
            raise ValidationError("Application period has ended")
        
        # Check if already applied
        existing_result = await self.db.execute(
            select(ScholarshipApplication).where(
                and_(
                    ScholarshipApplication.student_id == student_id,
                    ScholarshipApplication.scholarship_id == scholarship_id
                )
            )
        )
        
        if existing_result.scalar_one_or_none():
            raise ConflictError("Already applied for this scholarship")
        
        # Get student profile
        student_result = await self.db.execute(
            select(Student).where(Student.id == student_id)
        )
        student = student_result.scalar_one_or_none()
        
        if not student:
            raise NotFoundError("Student")
        
        # Calculate eligibility score
        eligibility_score = await self._calculate_eligibility_score(student, scholarship)
        
        # Create application
        application = ScholarshipApplication(
            student_id=student_id,
            scholarship_id=scholarship_id,
            applied_as_name=student.user.full_name,
            applied_as_email=student.user.email,
            applied_as_phone=student.user.phone_number or "",
            current_cgpa_at_apply=student.current_cgpa,
            percentage_at_apply=student.last_semester_percentage,
            family_income_at_apply=student.family_annual_income,
            application_data=application_data,
            eligibility_score=eligibility_score,
            match_score=await self._calculate_match_score(student, scholarship),
            status=ApplicationStatus.SUBMITTED
        )
        
        self.db.add(application)
        
        # Update scholarship application count
        scholarship.total_applications += 1
        await self.db.commit()
        await self.db.refresh(application)
        
        logger.info(f"Created scholarship application: {application.id}")
        return application
    
    async def get_student_applications(
        self,
        student_id: uuid.UUID,
        status: Optional[ApplicationStatus] = None
    ) -> List[ScholarshipApplication]:
        """Get all scholarship applications for a student"""
        query = select(ScholarshipApplication).where(
            ScholarshipApplication.student_id == student_id
        )
        
        if status:
            query = query.where(ScholarshipApplication.status == status)
        
        query = query.order_by(desc(ScholarshipApplication.applied_at))
        
        result = await self.db.execute(query)
        return list(result.scalars().all())