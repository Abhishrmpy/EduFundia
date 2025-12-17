from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import uuid
import logging

from ...core.database import get_db
from ...core.security import get_current_user
from ...schemas.student import StudentCreate, StudentUpdate, StudentResponse, StudentFinancialSummary, RiskAssessment
from ...services.auth_service import AuthService
from ...services.expense_service import ExpenseService
from ...services.risk_service import RiskService

router = APIRouter(prefix="/students", tags=["students"])
logger = logging.getLogger(__name__)


@router.post("/profile", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student_profile(
    student_data: StudentCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create or update student profile"""
    auth_service = AuthService(db)
    
    try:
        # Get user
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check if student profile already exists
        from ...models.student import Student
        from sqlalchemy import select
        
        result = await db.execute(
            select(Student).where(Student.user_id == user.id)
        )
        existing_student = result.scalar_one_or_none()
        
        if existing_student:
            # Update existing profile
            for field, value in student_data.dict(exclude_unset=True).items():
                setattr(existing_student, field, value)
            
            existing_student.profile_completed = True
            existing_student.profile_completed_at = datetime.utcnow()
            
            await db.commit()
            await db.refresh(existing_student)
            
            logger.info(f"Updated student profile: {existing_student.enrollment_number}")
            return StudentResponse.from_orm(existing_student)
        
        # Create new student profile
        from ...models.student import Student, CasteCategory, Gender
        from datetime import datetime
        
        student = Student(
            user_id=user.id,
            enrollment_number=student_data.enrollment_number,
            university_name=student_data.university_name,
            college_name=student_data.college_name,
            course_name=student_data.course_name,
            course_duration=student_data.course_duration,
            current_year=student_data.current_year,
            specialization=student_data.specialization,
            current_cgpa=student_data.current_cgpa,
            last_semester_percentage=student_data.last_semester_percentage,
            date_of_birth=student_data.date_of_birth,
            gender=Gender(student_data.gender),
            caste_category=CasteCategory(student_data.caste_category),
            permanent_address=student_data.permanent_address,
            current_address=student_data.current_address,
            city=student_data.city,
            state=student_data.state,
            pincode=student_data.pincode,
            country=student_data.country,
            father_name=student_data.father_name,
            mother_name=student_data.mother_name,
            guardian_name=student_data.guardian_name,
            guardian_phone=student_data.guardian_phone,
            guardian_relationship=student_data.guardian_relationship,
            family_annual_income=student_data.family_annual_income,
            monthly_allowance=student_data.monthly_allowance,
            has_education_loan=student_data.has_education_loan,
            education_loan_amount=student_data.education_loan_amount,
            education_loan_emi=student_data.education_loan_emi,
            has_part_time_job=student_data.has_part_time_job,
            part_time_income=student_data.part_time_income,
            has_family_business=student_data.has_family_business,
            profile_completed=True,
            profile_completed_at=datetime.utcnow(),
        )
        
        db.add(student)
        await db.commit()
        await db.refresh(student)
        
        # Update user profile completion status
        user.profile_completed = True
        await db.commit()
        
        logger.info(f"Created student profile: {student.enrollment_number}")
        return StudentResponse.from_orm(student)
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Create student profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create student profile: {str(e)}"
        )


@router.get("/profile", response_model=StudentResponse)
async def get_student_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get student profile"""
    auth_service = AuthService(db)
    
    try:
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
                detail="Student profile not found. Please complete your profile."
            )
        
        return StudentResponse.from_orm(student)
        
    except Exception as e:
        logger.error(f"Get student profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put("/profile", response_model=StudentResponse)
async def update_student_profile(
    student_update: StudentUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update student profile"""
    auth_service = AuthService(db)
    
    try:
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
        
        # Update fields
        update_dict = student_update.dict(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(student, field, value)
        
        await db.commit()
        await db.refresh(student)
        
        logger.info(f"Updated student profile: {student.enrollment_number}")
        return StudentResponse.from_orm(student)
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Update student profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/financial-summary", response_model=StudentFinancialSummary)
async def get_financial_summary(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get student's financial summary"""
    auth_service = AuthService(db)
    
    try:
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
        
        # Get expense service
        expense_service = ExpenseService(db)
        
        # Calculate summary
        from datetime import date, timedelta
        
        # Last 30 days expenses
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        expense_summary = await expense_service.get_expense_summary(
            student_id=student.id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Calculate income (monthly allowance or estimate)
        monthly_income = student.monthly_allowance or (student.family_annual_income / 12)
        
        # Calculate net balance
        net_balance = monthly_income - expense_summary.monthly_total
        
        # Calculate savings rate
        savings_rate = (net_balance / monthly_income * 100) if monthly_income > 0 else 0
        
        # Expense to income ratio
        expense_to_income_ratio = (expense_summary.monthly_total / monthly_income) if monthly_income > 0 else 0
        
        # Find biggest expense category
        biggest_category = max(
            expense_summary.category_breakdown.items(),
            key=lambda x: x[1],
            default=("None", 0)
        )
        
        return StudentFinancialSummary(
            total_expenses=expense_summary.total_expenses,
            total_income=monthly_income,
            net_balance=net_balance,
            monthly_average_expense=expense_summary.daily_average * 30,
            monthly_average_income=monthly_income,
            biggest_expense_category=biggest_category[0],
            biggest_expense_amount=biggest_category[1],
            savings_rate=savings_rate,
            expense_to_income_ratio=expense_to_income_ratio
        )
        
    except Exception as e:
        logger.error(f"Get financial summary error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/risk-assessment", response_model=RiskAssessment)
async def get_risk_assessment(
    use_ai: bool = Query(True, description="Use AI for risk assessment"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get student's financial risk assessment"""
    auth_service = AuthService(db)
    
    try:
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
        
        # Get risk assessment
        risk_service = RiskService(db)
        risk_assessment = await risk_service.get_risk_assessment(
            student_id=student.id,
            use_ai=use_ai
        )
        
        # Update student's risk scores in database
        await risk_service.update_student_risk_scores(student.id)
        
        return risk_assessment
        
    except Exception as e:
        logger.error(f"Get risk assessment error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/documents")
async def get_student_documents(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get student's uploaded documents"""
    auth_service = AuthService(db)
    
    try:
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
        
        # Extract document URLs
        documents = []
        
        if student.aadhar_card_url:
            documents.append({
                "type": "aadhar_card",
                "name": "Aadhar Card",
                "url": student.aadhar_card_url,
                "verified": True  # Assuming uploaded documents are verified
            })
        
        if student.income_certificate_url:
            documents.append({
                "type": "income_certificate",
                "name": "Income Certificate",
                "url": student.income_certificate_url,
                "verified": True
            })
        
        if student.caste_certificate_url:
            documents.append({
                "type": "caste_certificate",
                "name": "Caste Certificate",
                "url": student.caste_certificate_url,
                "verified": True
            })
        
        if student.marksheet_10th_url:
            documents.append({
                "type": "marksheet_10th",
                "name": "10th Marksheet",
                "url": student.marksheet_10th_url,
                "verified": True
            })
        
        if student.marksheet_12th_url:
            documents.append({
                "type": "marksheet_12th",
                "name": "12th Marksheet",
                "url": student.marksheet_12th_url,
                "verified": True
            })
        
        if student.college_id_card_url:
            documents.append({
                "type": "college_id",
                "name": "College ID Card",
                "url": student.college_id_card_url,
                "verified": True
            })
        
        if student.bank_passbook_url:
            documents.append({
                "type": "bank_passbook",
                "name": "Bank Passbook",
                "url": student.bank_passbook_url,
                "verified": True
            })
        
        return {
            "student_id": str(student.id),
            "documents": documents,
            "total_documents": len(documents)
        }
        
    except Exception as e:
        logger.error(f"Get documents error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/documents/{document_type}")
async def upload_document(
    document_type: str,
    document_url: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload student document"""
    auth_service = AuthService(db)
    
    try:
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
        
        # Map document type to field
        document_fields = {
            "aadhar_card": "aadhar_card_url",
            "income_certificate": "income_certificate_url",
            "caste_certificate": "caste_certificate_url",
            "marksheet_10th": "marksheet_10th_url",
            "marksheet_12th": "marksheet_12th_url",
            "college_id": "college_id_card_url",
            "bank_passbook": "bank_passbook_url"
        }
        
        if document_type not in document_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid document type. Allowed: {', '.join(document_fields.keys())}"
            )
        
        # Update document URL
        field_name = document_fields[document_type]
        setattr(student, field_name, document_url)
        
        await db.commit()
        
        logger.info(f"Uploaded document {document_type} for student {student.enrollment_number}")
        return {
            "message": "Document uploaded successfully",
            "document_type": document_type,
            "url": document_url
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Upload document error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Admin endpoints for college administration
@router.get("/college/{college_name}")
async def get_students_by_college(
    college_name: str,
    skip: int = 0,
    limit: int = 100,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get students by college (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        from ...models.student import Student
        from sqlalchemy import select, func
        
        # Search for college (case-insensitive, partial match)
        result = await db.execute(
            select(Student)
            .where(func.lower(Student.college_name).contains(college_name.lower()))
            .offset(skip)
            .limit(limit)
            .order_by(Student.created_at.desc())
        )
        
        students = result.scalars().all()
        
        return [
            {
                "id": str(student.id),
                "enrollment_number": student.enrollment_number,
                "full_name": student.user.full_name,
                "email": student.user.email,
                "course": student.course_name,
                "current_year": student.current_year,
                "financial_stress_score": student.financial_stress_score,
                "dropout_risk_score": student.dropout_risk_score,
                "family_income": student.family_annual_income,
                "created_at": student.created_at
            }
            for student in students
        ]
        
    except Exception as e:
        logger.error(f"Get students by college error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/at-risk")
async def get_at_risk_students(
    threshold: float = Query(70.0, ge=0, le=100, description="Risk threshold"),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get students at risk (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        risk_service = RiskService(db)
        at_risk_students = await risk_service.get_at_risk_students(
            threshold=threshold,
            limit=limit
        )
        
        return {
            "threshold": threshold,
            "count": len(at_risk_students),
            "students": at_risk_students
        }
        
    except Exception as e:
        logger.error(f"Get at-risk students error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )