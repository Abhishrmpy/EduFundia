from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
from datetime import date
import uuid
import logging

from ...core.database import get_db
from ...core.security import get_current_user
from ...schemas.scholarship import ScholarshipResponse, ScholarshipFilter, ScholarshipMatch
from ...services.auth_service import AuthService
from ...services.scholarship_service import ScholarshipService
from ...services.notification_service import NotificationService

router = APIRouter(prefix="/scholarships", tags=["scholarships"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=List[ScholarshipResponse])
async def get_scholarships(
    scholarship_type: Optional[str] = Query(None, description="Scholarship type filter"),
    min_amount: Optional[float] = Query(None, gt=0, description="Minimum amount"),
    max_amount: Optional[float] = Query(None, gt=0, description="Maximum amount"),
    eligible_caste: Optional[str] = Query(None, description="Caste eligibility"),
    eligible_gender: Optional[str] = Query(None, description="Gender eligibility"),
    eligible_course: Optional[str] = Query(None, description="Course eligibility"),
    eligible_state: Optional[str] = Query(None, description="State eligibility"),
    application_deadline_soon: Optional[bool] = Query(None, description="Show soon-to-close scholarships"),
    is_featured: Optional[bool] = Query(None, description="Show featured scholarships"),
    search_query: Optional[str] = Query(None, description="Search by name or provider"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db)
):
    """Get scholarships with filters"""
    scholarship_service = ScholarshipService(db)
    
    try:
        # Create filter
        scholarship_filter = ScholarshipFilter(
            scholarship_type=scholarship_type,
            min_amount=min_amount,
            max_amount=max_amount,
            eligible_caste=eligible_caste,
            eligible_gender=eligible_gender,
            eligible_course=eligible_course,
            eligible_state=eligible_state,
            application_deadline_soon=application_deadline_soon,
            is_featured=is_featured,
            search_query=search_query
        )
        
        # Get scholarships
        scholarships = await scholarship_service.get_all_scholarships(
            filters=scholarship_filter,
            limit=limit,
            offset=skip
        )
        
        return [ScholarshipResponse.from_orm(scholarship) for scholarship in scholarships]
        
    except Exception as e:
        logger.error(f"Get scholarships error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/match", response_model=List[ScholarshipMatch])
async def match_scholarships(
    limit: int = Query(20, ge=1, le=100, description="Number of matches to return"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get scholarships that match student's profile"""
    auth_service = AuthService(db)
    scholarship_service = ScholarshipService(db)
    
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
                detail="Student profile not found. Please complete your profile."
            )
        
        # Match scholarships
        matches = await scholarship_service.match_scholarships_for_student(
            student_id=student.id,
            limit=limit
        )
        
        return matches
        
    except Exception as e:
        logger.error(f"Match scholarships error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{scholarship_id}", response_model=ScholarshipResponse)
async def get_scholarship(
    scholarship_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get specific scholarship by ID"""
    scholarship_service = ScholarshipService(db)
    
    try:
        scholarship = await scholarship_service.get_scholarship_by_id(scholarship_id)
        if not scholarship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scholarship not found"
            )
        
        return ScholarshipResponse.from_orm(scholarship)
        
    except Exception as e:
        logger.error(f"Get scholarship error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{scholarship_id}/match-score")
async def get_scholarship_match_score(
    scholarship_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get match score for a specific scholarship"""
    auth_service = AuthService(db)
    scholarship_service = ScholarshipService(db)
    
    try:
        # Get scholarship
        scholarship = await scholarship_service.get_scholarship_by_id(scholarship_id)
        if not scholarship:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scholarship not found"
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
        
        # Calculate match score
        eligibility_score = await scholarship_service._calculate_eligibility_score(student, scholarship)
        match_score = await scholarship_service._calculate_match_score(student, scholarship)
        
        # Get match reasons
        reasons = scholarship_service._get_match_reasons(student, scholarship, match_score)
        
        # Check if already applied
        from ...models.scholarship import ScholarshipApplication
        from sqlalchemy import select, and_
        
        app_result = await db.execute(
            select(ScholarshipApplication).where(
                and_(
                    ScholarshipApplication.student_id == student.id,
                    ScholarshipApplication.scholarship_id == scholarship_id
                )
            )
        )
        existing_app = app_result.scalar_one_or_none()
        
        application_status = "not_applied"
        if existing_app:
            application_status = existing_app.status.value
        
        return {
            "scholarship_id": str(scholarship_id),
            "scholarship_name": scholarship.name,
            "eligibility_score": eligibility_score,
            "match_score": match_score,
            "reasons": reasons,
            "application_status": application_status,
            "deadline_days": (scholarship.application_end_date - date.today()).days,
            "documents_required": scholarship.documents_required or []
        }
        
    except Exception as e:
        logger.error(f"Get match score error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{scholarship_id}/apply")
async def apply_for_scholarship(
    scholarship_id: uuid.UUID,
    application_data: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """Apply for a scholarship"""
    auth_service = AuthService(db)
    scholarship_service = ScholarshipService(db)
    
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
        
        # Apply for scholarship
        application = await scholarship_service.create_application(
            student_id=student.id,
            scholarship_id=scholarship_id,
            application_data=application_data
        )
        
        # Send notification in background
        if background_tasks:
            background_tasks.add_task(
                send_scholarship_application_notification,
                user.id,
                application.id
            )
        
        return {
            "message": "Application submitted successfully",
            "application_id": str(application.id),
            "status": application.status.value
        }
        
    except Exception as e:
        logger.error(f"Apply for scholarship error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/applications")
async def get_scholarship_applications(
    status: Optional[str] = Query(None, description="Application status filter"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get student's scholarship applications"""
    auth_service = AuthService(db)
    scholarship_service = ScholarshipService(db)
    
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
        
        # Get applications
        from ...models.scholarship import ApplicationStatus
        
        status_enum = None
        if status:
            try:
                status_enum = ApplicationStatus(status)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status}"
                )
        
        applications = await scholarship_service.get_student_applications(
            student_id=student.id,
            status=status_enum
        )
        
        # Format response
        result = []
        for app in applications:
            result.append({
                "application_id": str(app.id),
                "scholarship_id": str(app.scholarship_id),
                "scholarship_name": app.scholarship.name,
                "applied_at": app.applied_at,
                "status": app.status.value,
                "eligibility_score": app.eligibility_score,
                "match_score": app.match_score,
                "awarded_amount": app.awarded_amount,
                "disbursement_date": app.disbursement_date,
                "deadline": app.scholarship.application_end_date,
                "days_until_deadline": (app.scholarship.application_end_date - date.today()).days
            })
        
        return {
            "student_id": str(student.id),
            "total_applications": len(result),
            "applications": result
        }
        
    except Exception as e:
        logger.error(f"Get applications error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/applications/{application_id}")
async def get_application_details(
    application_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get scholarship application details"""
    auth_service = AuthService(db)
    
    try:
        # Get application
        from ...models.scholarship import ScholarshipApplication
        from sqlalchemy import select
        
        result = await db.execute(
            select(ScholarshipApplication).where(ScholarshipApplication.id == application_id)
        )
        application = result.scalar_one_or_none()
        
        if not application:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Application not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or application.student.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this application"
            )
        
        # Format response
        return {
            "application_id": str(application.id),
            "scholarship": {
                "id": str(application.scholarship_id),
                "name": application.scholarship.name,
                "provider": application.scholarship.provider_name,
                "amount": application.scholarship.amount,
                "application_end_date": application.scholarship.application_end_date,
                "result_date": application.scholarship.result_date
            },
            "student": {
                "name": application.applied_as_name,
                "email": application.applied_as_email,
                "phone": application.applied_as_phone
            },
            "academic_snapshot": {
                "cgpa": application.current_cgpa_at_apply,
                "percentage": application.percentage_at_apply
            },
            "financial_snapshot": {
                "family_income": application.family_income_at_apply
            },
            "application_data": application.application_data,
            "status": application.status.value,
            "eligibility_score": application.eligibility_score,
            "match_score": application.match_score,
            "reviewer_notes": application.reviewer_notes,
            "awarded_amount": application.awarded_amount,
            "disbursement_date": application.disbursement_date,
            "applied_at": application.applied_at,
            "updated_at": application.updated_at
        }
        
    except Exception as e:
        logger.error(f"Get application details error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/deadlines/upcoming")
async def get_upcoming_deadlines(
    days: int = Query(30, ge=1, le=365, description="Lookahead days"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get scholarships with upcoming deadlines"""
    scholarship_service = ScholarshipService(db)
    
    try:
        # Get scholarships with deadlines in next X days
        from ...models.scholarship import Scholarship, ScholarshipStatus
        from sqlalchemy import select, and_
        from datetime import date, timedelta
        
        deadline_date = date.today() + timedelta(days=days)
        
        result = await db.execute(
            select(Scholarship).where(
                and_(
                    Scholarship.status == ScholarshipStatus.ACTIVE,
                    Scholarship.application_end_date <= deadline_date,
                    Scholarship.application_end_date >= date.today()
                )
            ).order_by(Scholarship.application_end_date)
            .limit(100)
        )
        
        scholarships = result.scalars().all()
        
        return [
            {
                "id": str(scholarship.id),
                "name": scholarship.name,
                "provider": scholarship.provider_name,
                "amount": scholarship.amount,
                "application_end_date": scholarship.application_end_date,
                "days_remaining": (scholarship.application_end_date - date.today()).days,
                "is_featured": scholarship.is_featured
            }
            for scholarship in scholarships
        ]
        
    except Exception as e:
        logger.error(f"Get upcoming deadlines error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/stats")
async def get_scholarship_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get scholarship statistics for student"""
    auth_service = AuthService(db)
    
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
        
        # Get statistics
        from ...models.scholarship import ScholarshipApplication, ApplicationStatus
        from sqlalchemy import select, func
        
        # Total applications
        total_result = await db.execute(
            select(func.count(ScholarshipApplication.id)).where(
                ScholarshipApplication.student_id == student.id
            )
        )
        total_applications = total_result.scalar() or 0
        
        # Applications by status
        status_result = await db.execute(
            select(
                ScholarshipApplication.status,
                func.count(ScholarshipApplication.id).label("count")
            ).where(
                ScholarshipApplication.student_id == student.id
            ).group_by(ScholarshipApplication.status)
        )
        
        by_status = {}
        for row in status_result:
            by_status[row[0].value] = row[1]
        
        # Total awarded amount
        awarded_result = await db.execute(
            select(func.coalesce(func.sum(ScholarshipApplication.awarded_amount), 0)).where(
                and_(
                    ScholarshipApplication.student_id == student.id,
                    ScholarshipApplication.awarded_amount.isnot(None)
                )
            )
        )
        total_awarded = float(awarded_result.scalar() or 0)
        
        # Success rate
        successful_apps = by_status.get("awarded", 0) + by_status.get("disbursed", 0)
        success_rate = (successful_apps / total_applications * 100) if total_applications > 0 else 0
        
        return {
            "student_id": str(student.id),
            "total_applications": total_applications,
            "applications_by_status": by_status,
            "total_awarded_amount": total_awarded,
            "success_rate": round(success_rate, 2),
            "scholarships_awarded": successful_apps,
            "pending_applications": by_status.get("submitted", 0) + by_status.get("under_review", 0)
        }
        
    except Exception as e:
        logger.error(f"Get scholarship stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Admin endpoints
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_scholarship(
    scholarship_data: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new scholarship (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    scholarship_service = ScholarshipService(db)
    
    try:
        from ...schemas.scholarship import ScholarshipCreate
        from datetime import datetime
        
        # Convert date strings to date objects
        if "application_start_date" in scholarship_data:
            scholarship_data["application_start_date"] = datetime.strptime(
                scholarship_data["application_start_date"], "%Y-%m-%d"
            ).date()
        
        if "application_end_date" in scholarship_data:
            scholarship_data["application_end_date"] = datetime.strptime(
                scholarship_data["application_end_date"], "%Y-%m-%d"
            ).date()
        
        # Create scholarship
        scholarship = await scholarship_service.create_scholarship(
            ScholarshipCreate(**scholarship_data)
        )
        
        return {
            "message": "Scholarship created successfully",
            "scholarship_id": str(scholarship.id),
            "scholarship": ScholarshipResponse.from_orm(scholarship)
        }
        
    except Exception as e:
        logger.error(f"Create scholarship error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


async def send_scholarship_application_notification(user_id: uuid.UUID, application_id: uuid.UUID):
    """Background task to send scholarship application notification"""
    # This would be implemented with Celery or similar task queue
    # For now, it's a placeholder for notification logic
    
    logger.info(f"Sending scholarship application notification for user {user_id}, application {application_id}")
    pass