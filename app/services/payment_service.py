from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import selectinload
import uuid
import random
import logging

from ..models.payment import Payment, PaymentStatus, PaymentMethod, PaymentType
from ..models.student import Student
from ..models.user import User
from ..schemas.payment import PaymentCreate, PaymentUpdate, PaymentSimulation
from ..core.exceptions import NotFoundError, ValidationError
from ..services.notification_service import NotificationService

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notification_service = NotificationService(db)
    
    async def create_payment(self, payment_data: PaymentCreate) -> Payment:
        """Create a new payment record"""
        # Validate amount
        if payment_data.amount <= 0:
            raise ValidationError("Payment amount must be positive")
        
        # Generate unique payment reference
        payment_reference = self._generate_payment_reference()
        
        # Calculate net amount (amount - fees)
        gateway_fee = self._calculate_gateway_fee(
            payment_data.amount,
            payment_data.payment_method
        )
        tax_amount = self._calculate_tax(payment_data.amount)
        net_amount = payment_data.amount - gateway_fee - tax_amount
        
        # Create payment
        payment = Payment(
            user_id=payment_data.user_id,
            student_id=payment_data.student_id,
            payment_reference=payment_reference,
            amount=payment_data.amount,
            currency=payment_data.currency,
            payment_type=payment_data.payment_type,
            description=payment_data.description,
            recipient_name=payment_data.recipient_name,
            recipient_account=payment_data.recipient_account,
            payment_method=payment_data.payment_method,
            gateway_name=payment_data.gateway_name or "Simulated Gateway",
            gateway_fee=gateway_fee,
            tax_amount=tax_amount,
            net_amount=net_amount,
            status=PaymentStatus.PENDING,
        )
        
        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)
        
        logger.info(f"Created payment: {payment_reference} - ₹{payment.amount}")
        return payment
    
    def _generate_payment_reference(self) -> str:
        """Generate a unique payment reference"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        random_str = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=6))
        return f"PAY{timestamp}{random_str}"
    
    def _calculate_gateway_fee(self, amount: float, method: PaymentMethod) -> float:
        """Calculate gateway fee based on payment method"""
        fees = {
            PaymentMethod.UPI: 0.0,  # UPI is free
            PaymentMethod.CREDIT_CARD: amount * 0.018,  # 1.8%
            PaymentMethod.DEBIT_CARD: amount * 0.01,    # 1.0%
            PaymentMethod.NET_BANKING: amount * 0.02,   # 2.0%
            PaymentMethod.WALLET: amount * 0.015,       # 1.5%
            PaymentMethod.BANK_TRANSFER: 10.0,          # Flat ₹10
            PaymentMethod.CASH: 0.0,
            PaymentMethod.SCHOLARSHIP: 0.0,
            PaymentMethod.LOAN: 0.0,
        }
        return fees.get(method, amount * 0.02)  # Default 2%
    
    def _calculate_tax(self, amount: float) -> float:
        """Calculate GST (18%) on gateway fee"""
        # GST is 18% on gateway fees
        return amount * 0.18
    
    async def simulate_payment(
        self,
        payment_id: uuid.UUID,
        simulation_data: PaymentSimulation
    ) -> Payment:
        """Simulate a payment (for development/testing)"""
        payment = await self.get_payment_by_id(payment_id)
        if not payment:
            raise NotFoundError("Payment")
        
        # Validate simulation data based on payment method
        if payment.payment_method == PaymentMethod.UPI and not simulation_data.upi_id:
            raise ValidationError("UPI ID is required for UPI payments")
        
        if payment.payment_method in [PaymentMethod.CREDIT_CARD, PaymentMethod.DEBIT_CARD]:
            if not simulation_data.card_number or not simulation_data.card_expiry or not simulation_data.card_cvv:
                raise ValidationError("Card details are required for card payments")
        
        if payment.payment_method == PaymentMethod.NET_BANKING:
            if not simulation_data.bank_account or not simulation_data.ifsc_code:
                raise ValidationError("Bank account details are required for net banking")
        
        # Simulate payment processing
        payment.status = PaymentStatus.PROCESSING
        payment.gateway_reference = f"SIM{random.randint(100000, 999999)}"
        payment.processed_at = datetime.utcnow()
        await self.db.commit()
        
        # Simulate processing delay
        await asyncio.sleep(2)
        
        # Randomly determine success/failure (90% success rate for simulation)
        if random.random() < 0.9:
            payment.status = PaymentStatus.SUCCESS
            payment.completed_at = datetime.utcnow()
            payment.verification_status = "verified"
            payment.verified_at = datetime.utcnow()
            
            # Send success notification
            await self._send_payment_success_notification(payment)
        else:
            payment.status = PaymentStatus.FAILED
            payment.error_code = random.choice(["INSUFFICIENT_FUNDS", "NETWORK_ERROR", "DECLINED"])
            payment.error_message = "Payment failed during simulation"
        
        await self.db.commit()
        await self.db.refresh(payment)
        
        logger.info(f"Simulated payment {payment.payment_reference}: {payment.status}")
        return payment
    
    async def _send_payment_success_notification(self, payment: Payment):
        """Send payment success notification"""
        try:
            # Get user for notification
            user_result = await self.db.execute(
                select(User).where(User.id == payment.user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if user and user.notifications_enabled:
                await self.notification_service.create_notification(
                    NotificationCreate(
                        user_id=user.id,
                        title="✅ Payment Successful",
                        message=f"Your payment of ₹{payment.amount:.2f} has been processed successfully.",
                        notification_type="payment_reminder",
                        priority="medium",
                        data={
                            "payment_reference": payment.payment_reference,
                            "amount": payment.amount,
                            "status": "success"
                        }
                    )
                )
        except Exception as e:
            logger.error(f"Failed to send payment notification: {e}")
    
    async def get_payment_by_id(self, payment_id: uuid.UUID) -> Optional[Payment]:
        """Get payment by ID"""
        result = await self.db.execute(
            select(Payment).where(Payment.id == payment_id)
        )
        return result.scalar_one_or_none()
    
    async def get_payment_by_reference(self, payment_reference: str) -> Optional[Payment]:
        """Get payment by reference number"""
        result = await self.db.execute(
            select(Payment).where(Payment.payment_reference == payment_reference)
        )
        return result.scalar_one_or_none()
    
    async def get_student_payments(
        self,
        student_id: uuid.UUID,
        status: Optional[PaymentStatus] = None,
        payment_type: Optional[PaymentType] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Payment]:
        """Get payments for a student"""
        query = select(Payment).where(Payment.student_id == student_id)
        
        if status:
            query = query.where(Payment.status == status)
        if payment_type:
            query = query.where(Payment.payment_type == payment_type)
        if start_date:
            query = query.where(Payment.payment_date >= start_date)
        if end_date:
            query = query.where(Payment.payment_date <= end_date)
        
        query = query.order_by(desc(Payment.payment_date))
        query = query.offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        return list(result.scalars().all())
    
    async def update_payment_status(
        self,
        payment_id: uuid.UUID,
        status: PaymentStatus,
        gateway_reference: Optional[str] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> Payment:
        """Update payment status (for webhooks)"""
        payment = await self.get_payment_by_id(payment_id)
        if not payment:
            raise NotFoundError("Payment")
        
        payment.status = status
        
        if gateway_reference:
            payment.gateway_reference = gateway_reference
        
        if status == PaymentStatus.SUCCESS:
            payment.completed_at = datetime.utcnow()
            payment.verification_status = "verified"
            payment.verified_at = datetime.utcnow()
        elif status == PaymentStatus.FAILED and error_details:
            payment.error_code = error_details.get("error_code")
            payment.error_message = error_details.get("error_message")
        elif status == PaymentStatus.PROCESSING:
            payment.processed_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(payment)
        
        logger.info(f"Updated payment {payment.payment_reference} to {status}")
        return payment
    
    async def get_payment_summary(self, student_id: uuid.UUID) -> Dict[str, Any]:
        """Get payment summary for a student"""
        # Total payments
        total_result = await self.db.execute(
            select(
                func.coalesce(func.sum(Payment.amount), 0).label("total_amount"),
                func.count(Payment.id).label("total_count")
            ).where(
                and_(
                    Payment.student_id == student_id,
                    Payment.status == PaymentStatus.SUCCESS
                )
            )
        )
        
        total_row = total_result.first()
        total_amount = float(total_row[0] or 0)
        total_count = total_row[1] or 0
        
        # Payments by type
        type_result = await self.db.execute(
            select(
                Payment.payment_type,
                func.coalesce(func.sum(Payment.amount), 0).label("type_amount"),
                func.count(Payment.id).label("type_count")
            ).where(
                and_(
                    Payment.student_id == student_id,
                    Payment.status == PaymentStatus.SUCCESS
                )
            ).group_by(Payment.payment_type)
        )
        
        by_type = {}
        for row in type_result:
            by_type[row[0].value] = {
                "amount": float(row[1]),
                "count": row[2]
            }
        
        # Recent payments (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_result = await self.db.execute(
            select(
                func.coalesce(func.sum(Payment.amount), 0).label("recent_amount"),
                func.count(Payment.id).label("recent_count")
            ).where(
                and_(
                    Payment.student_id == student_id,
                    Payment.status == PaymentStatus.SUCCESS,
                    Payment.payment_date >= thirty_days_ago
                )
            )
        )
        
        recent_row = recent_result.first()
        recent_amount = float(recent_row[0] or 0)
        recent_count = recent_row[1] or 0
        
        return {
            "total_amount": total_amount,
            "total_count": total_count,
            "average_payment": total_amount / total_count if total_count > 0 else 0,
            "payments_by_type": by_type,
            "recent_amount": recent_amount,
            "recent_count": recent_count,
            "monthly_average": recent_amount / 30 if recent_amount > 0 else 0
        }
    
    async def process_webhook(
        self,
        webhook_data: Dict[str, Any],
        signature: Optional[str] = None
    ) -> Payment:
        """Process payment webhook from payment gateway"""
        # In production, verify the webhook signature here
        
        payment_reference = webhook_data.get("payment_reference")
        if not payment_reference:
            raise ValidationError("Payment reference is required")
        
        payment = await self.get_payment_by_reference(payment_reference)
        if not payment:
            raise NotFoundError("Payment")
        
        status = webhook_data.get("status")
        if not status:
            raise ValidationError("Status is required")
        
        try:
            payment_status = PaymentStatus(status.lower())
        except ValueError:
            raise ValidationError(f"Invalid status: {status}")
        
        error_details = None
        if payment_status == PaymentStatus.FAILED:
            error_details = {
                "error_code": webhook_data.get("error_code"),
                "error_message": webhook_data.get("error_message")
            }
        
        return await self.update_payment_status(
            payment_id=payment.id,
            status=payment_status,
            gateway_reference=webhook_data.get("gateway_reference"),
            error_details=error_details
        )
    
    async def create_refund(
        self,
        original_payment_id: uuid.UUID,
        refund_amount: float,
        reason: str
    ) -> Payment:
        """Create a refund payment"""
        original_payment = await self.get_payment_by_id(original_payment_id)
        if not original_payment:
            raise NotFoundError("Original payment")
        
        if original_payment.status != PaymentStatus.SUCCESS:
            raise ValidationError("Can only refund successful payments")
        
        if refund_amount <= 0 or refund_amount > original_payment.amount:
            raise ValidationError("Invalid refund amount")
        
        # Create refund payment
        refund_data = PaymentCreate(
            user_id=original_payment.user_id,
            student_id=original_payment.student_id,
            amount=refund_amount,
            currency=original_payment.currency,
            payment_type=PaymentType.REFUND,
            description=f"Refund for {original_payment.description}. Reason: {reason}",
            recipient_name=original_payment.recipient_name,
            recipient_account=original_payment.recipient_account,
            payment_method=original_payment.payment_method,
            gateway_name=original_payment.gateway_name,
        )
        
        refund_payment = await self.create_payment(refund_data)
        
        # Simulate refund processing (instant for simulation)
        refund_payment.status = PaymentStatus.SUCCESS
        refund_payment.completed_at = datetime.utcnow()
        refund_payment.verification_status = "verified"
        refund_payment.verified_at = datetime.utcnow()
        
        # Update original payment status
        if refund_amount == original_payment.amount:
            original_payment.status = PaymentStatus.REFUNDED
        else:
            original_payment.status = PaymentStatus.PARTIALLY_REFUNDED
        
        await self.db.commit()
        
        logger.info(f"Created refund: {refund_payment.payment_reference} for {original_payment.payment_reference}")
        return refund_payment