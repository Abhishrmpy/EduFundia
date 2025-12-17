from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict, Any
import uuid
import logging

from ...core.database import get_db
from ...core.security import get_current_user
from ...schemas.payment import PaymentCreate, PaymentUpdate, PaymentResponse, PaymentSimulation
from ...services.auth_service import AuthService
from ...services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    payment_data: PaymentCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new payment record"""
    auth_service = AuthService(db)
    payment_service = PaymentService(db)
    
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
        payment_data.user_id = user.id
        payment_data.student_id = student.id
        
        # Create payment
        payment = await payment_service.create_payment(payment_data)
        return PaymentResponse.from_orm(payment)
        
    except Exception as e:
        logger.error(f"Create payment error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{payment_id}/simulate", response_model=PaymentResponse)
async def simulate_payment(
    payment_id: uuid.UUID,
    simulation_data: PaymentSimulation,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Simulate payment processing (for development/testing)"""
    auth_service = AuthService(db)
    payment_service = PaymentService(db)
    
    try:
        # Get payment
        payment = await payment_service.get_payment_by_id(payment_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or payment.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to process this payment"
            )
        
        # Simulate payment
        simulated_payment = await payment_service.simulate_payment(payment_id, simulation_data)
        return PaymentResponse.from_orm(simulated_payment)
        
    except Exception as e:
        logger.error(f"Simulate payment error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=List[PaymentResponse])
async def get_payments(
    status: Optional[str] = Query(None, description="Payment status filter"),
    payment_type: Optional[str] = Query(None, description="Payment type filter"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get payments with filters"""
    auth_service = AuthService(db)
    payment_service = PaymentService(db)
    
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
        
        # Parse dates
        from datetime import datetime
        
        start_date_obj = None
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid start date format. Use YYYY-MM-DD"
                )
        
        end_date_obj = None
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid end date format. Use YYYY-MM-DD"
                )
        
        # Get payments
        from ...models.payment import PaymentStatus, PaymentType
        
        status_enum = None
        if status:
            try:
                status_enum = PaymentStatus(status.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status}"
                )
        
        type_enum = None
        if payment_type:
            try:
                type_enum = PaymentType(payment_type.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid payment type: {payment_type}"
                )
        
        payments = await payment_service.get_student_payments(
            student_id=student.id,
            status=status_enum,
            payment_type=type_enum,
            start_date=start_date_obj,
            end_date=end_date_obj,
            limit=limit,
            offset=skip
        )
        
        return [PaymentResponse.from_orm(payment) for payment in payments]
        
    except Exception as e:
        logger.error(f"Get payments error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{payment_id}", response_model=PaymentResponse)
async def get_payment(
    payment_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get specific payment by ID"""
    auth_service = AuthService(db)
    payment_service = PaymentService(db)
    
    try:
        # Get payment
        payment = await payment_service.get_payment_by_id(payment_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or payment.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this payment"
            )
        
        return PaymentResponse.from_orm(payment)
        
    except Exception as e:
        logger.error(f"Get payment error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/reference/{payment_reference}", response_model=PaymentResponse)
async def get_payment_by_reference(
    payment_reference: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get payment by reference number"""
    auth_service = AuthService(db)
    payment_service = PaymentService(db)
    
    try:
        # Get payment
        payment = await payment_service.get_payment_by_reference(payment_reference)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or payment.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this payment"
            )
        
        return PaymentResponse.from_orm(payment)
        
    except Exception as e:
        logger.error(f"Get payment by reference error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/summary")
async def get_payment_summary(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get payment summary and statistics"""
    auth_service = AuthService(db)
    payment_service = PaymentService(db)
    
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
        summary = await payment_service.get_payment_summary(student.id)
        
        return {
            "student_id": str(student.id),
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"Get payment summary error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/webhook")
async def payment_webhook(
    webhook_data: Dict[str, Any],
    signature: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Handle payment webhook from payment gateway"""
    payment_service = PaymentService(db)
    
    try:
        # Process webhook
        payment = await payment_service.process_webhook(webhook_data, signature)
        
        return {
            "message": "Webhook processed successfully",
            "payment_reference": payment.payment_reference,
            "status": payment.status.value,
            "verified": payment.verification_status == "verified"
        }
        
    except Exception as e:
        logger.error(f"Payment webhook error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/{payment_id}/refund")
async def create_refund(
    payment_id: uuid.UUID,
    refund_amount: float = Query(..., gt=0, description="Refund amount"),
    reason: str = Query(..., description="Refund reason"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a refund for a payment"""
    auth_service = AuthService(db)
    payment_service = PaymentService(db)
    
    try:
        # Get payment
        payment = await payment_service.get_payment_by_id(payment_id)
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        # Verify ownership
        user = await auth_service.get_user_by_firebase_uid(current_user["uid"])
        if not user or payment.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to refund this payment"
            )
        
        # Create refund
        refund = await payment_service.create_refund(payment_id, refund_amount, reason)
        
        return {
            "message": "Refund created successfully",
            "refund_id": str(refund.id),
            "refund_reference": refund.payment_reference,
            "amount": refund.amount,
            "status": refund.status.value
        }
        
    except Exception as e:
        logger.error(f"Create refund error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/test/simulation")
async def test_payment_simulation(
    amount: float = Query(1000.0, gt=0, description="Payment amount"),
    payment_method: str = Query("upi", description="Payment method"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Test payment simulation (for development)"""
    auth_service = AuthService(db)
    payment_service = PaymentService(db)
    
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
        
        # Create test payment
        from ...schemas.payment import PaymentCreate, PaymentType, PaymentMethod
        
        payment_data = PaymentCreate(
            user_id=user.id,
            student_id=student.id,
            amount=amount,
            payment_type=PaymentType.TUITION_FEE,
            description="Test payment for simulation",
            recipient_name="Test University",
            recipient_account="TEST001",
            payment_method=PaymentMethod(payment_method),
            gateway_name="Test Gateway"
        )
        
        payment = await payment_service.create_payment(payment_data)
        
        # Simulate payment
        simulation_data = PaymentSimulation(
            amount=amount,
            payment_method=PaymentMethod(payment_method),
            upi_id="test@upi" if payment_method == "upi" else None,
            card_number="4111111111111111" if payment_method in ["credit_card", "debit_card"] else None,
            card_expiry="12/25" if payment_method in ["credit_card", "debit_card"] else None,
            card_cvv="123" if payment_method in ["credit_card", "debit_card"] else None
        )
        
        simulated_payment = await payment_service.simulate_payment(payment.id, simulation_data)
        
        return {
            "message": "Payment simulation completed",
            "payment": PaymentResponse.from_orm(simulated_payment)
        }
        
    except Exception as e:
        logger.error(f"Test payment simulation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Admin endpoints
@router.get("/admin/all")
async def get_all_payments(
    student_id: Optional[uuid.UUID] = Query(None, description="Filter by student ID"),
    college: Optional[str] = Query(None, description="Filter by college"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all payments (admin only)"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    try:
        from ...models.payment import Payment
        from ...models.student import Student
        from sqlalchemy import select, join
        
        # Build query
        query = select(Payment)
        
        if student_id:
            query = query.where(Payment.student_id == student_id)
        
        if college:
            query = query.join(Student, Payment.student_id == Student.id)
            query = query.where(Student.college_name.ilike(f"%{college}%"))
        
        query = query.order_by(Payment.payment_date.desc())
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        payments = result.scalars().all()
        
        return [
            {
                "id": str(payment.id),
                "payment_reference": payment.payment_reference,
                "student_id": str(payment.student_id),
                "student_name": payment.student.user.full_name,
                "college": payment.student.college_name,
                "amount": payment.amount,
                "status": payment.status.value,
                "payment_method": payment.payment_method.value,
                "payment_date": payment.payment_date,
                "description": payment.description
            }
            for payment in payments
        ]
        
    except Exception as e:
        logger.error(f"Get all payments error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )