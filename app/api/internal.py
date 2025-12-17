from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from ..core.database import get_db, check_db_connection
from ..integrations.redis_client import redis_client
from ..integrations.firebase import firebase_service
from ..integrations.vertex_ai import vertex_ai_client

router = APIRouter(prefix="/internal", tags=["internal"])
logger = logging.getLogger(__name__)


@router.get("/health")
async def internal_health_check(
    db: AsyncSession = Depends(get_db)
):
    """Comprehensive health check for internal services"""
    health_status = {
        "api": "healthy",
        "database": "unknown",
        "redis": "unknown",
        "firebase": "unknown",
        "vertex_ai": "unknown",
        "overall": "unknown"
    }
    
    try:
        # Check database
        db_healthy = await check_db_connection()
        health_status["database"] = "healthy" if db_healthy else "unhealthy"
        
        # Check Redis
        redis_healthy = redis_client.is_connected()
        health_status["redis"] = "healthy" if redis_healthy else "unhealthy"
        
        # Check Firebase
        firebase_healthy = firebase_service._initialize_firebase() is not None
        health_status["firebase"] = "healthy" if firebase_healthy else "unhealthy (mock mode)"
        
        # Check Vertex AI
        vertex_ai_healthy = vertex_ai_client.initialized
        health_status["vertex_ai"] = "healthy" if vertex_ai_healthy else "unhealthy (fallback mode)"
        
        # Determine overall status
        critical_services = ["database"]
        unhealthy_services = [
            service for service, status in health_status.items() 
            if service != "overall" and status != "healthy" and "mock" not in status and "fallback" not in status
        ]
        
        # Check if any critical services are unhealthy
        critical_unhealthy = any(service in unhealthy_services for service in critical_services)
        
        if critical_unhealthy:
            health_status["overall"] = "unhealthy"
        elif unhealthy_services:
            health_status["overall"] = "degraded"
        else:
            health_status["overall"] = "healthy"
        
        return health_status
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        health_status["overall"] = "unhealthy"
        health_status["error"] = str(e)
        return health_status


@router.get("/metrics")
async def get_metrics(
    db: AsyncSession = Depends(get_db)
):
    """Get system metrics"""
    try:
        metrics = {}
        
        # Get database metrics
        from sqlalchemy import text
        
        # User count
        user_result = await db.execute(text("SELECT COUNT(*) FROM users"))
        metrics["user_count"] = user_result.scalar()
        
        # Student count
        student_result = await db.execute(text("SELECT COUNT(*) FROM students"))
        metrics["student_count"] = student_result.scalar()
        
        # Expense count
        expense_result = await db.execute(text("SELECT COUNT(*), SUM(amount) FROM expenses"))
        expense_row = expense_result.first()
        metrics["expense_count"] = expense_row[0] or 0
        metrics["total_expenses"] = float(expense_row[1] or 0)
        
        # Budget count
        budget_result = await db.execute(text("SELECT COUNT(*) FROM budgets"))
        metrics["budget_count"] = budget_result.scalar()
        
        # Scholarship count
        scholarship_result = await db.execute(text("SELECT COUNT(*) FROM scholarships"))
        metrics["scholarship_count"] = scholarship_result.scalar()
        
        # Redis metrics
        if redis_client.is_connected():
            redis_stats = await redis_client.get_cache_stats()
            metrics["redis"] = redis_stats
        else:
            metrics["redis"] = {"connected": False}
        
        return metrics
        
    except Exception as e:
        logger.error(f"Get metrics error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metrics: {str(e)}"
        )


@router.post("/cache/clear")
async def clear_cache(
    pattern: str = "*"
):
    """Clear Redis cache (admin only)"""
    try:
        if not redis_client.is_connected():
            return {"message": "Redis not connected", "cleared": 0}
        
        # Get keys matching pattern
        keys = await redis_client.keys(pattern)
        
        # Delete keys
        deleted_count = 0
        for key in keys:
            if await redis_client.delete(key):
                deleted_count += 1
        
        return {
            "message": f"Cache cleared for pattern: {pattern}",
            "deleted_keys": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Clear cache error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {str(e)}"
        )


@router.post("/notifications/cleanup")
async def cleanup_old_notifications(
    days_old: int = 90
):
    """Cleanup old notifications (admin only)"""
    try:
        from ..services.notification_service import NotificationService
        from ..core.database import get_db
        
        # Get database session
        from sqlalchemy.ext.asyncio import AsyncSession
        db: AsyncSession = get_db()
        
        # Create notification service
        notification_service = NotificationService(await db.__anext__())
        
        # Cleanup old notifications
        deleted_count = await notification_service.cleanup_old_notifications(days_old)
        
        return {
            "message": f"Cleaned up notifications older than {days_old} days",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        logger.error(f"Cleanup notifications error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup notifications: {str(e)}"
        )


@router.post("/risk/recalculate")
async def recalculate_all_risk_scores(
    threshold: float = 0.0
):
    """Recalculate risk scores for all students (admin only)"""
    try:
        from ..services.risk_service import RiskService
        from ..core.database import get_db
        
        # Get database session
        from sqlalchemy.ext.asyncio import AsyncSession
        db: AsyncSession = get_db()
        
        # Create risk service
        risk_service = RiskService(await db.__anext__())
        
        # Get all students
        from ..models.student import Student
        from sqlalchemy import select
        
        result = await db.execute(select(Student))
        students = result.scalars().all()
        
        # Recalculate scores
        updated_count = 0
        for student in students:
            try:
                await risk_service.update_student_risk_scores(student.id)
                updated_count += 1
            except Exception as e:
                logger.error(f"Failed to update risk scores for student {student.id}: {e}")
        
        return {
            "message": f"Recalculated risk scores for {updated_count} students",
            "total_students": len(students),
            "updated_count": updated_count
        }
        
    except Exception as e:
        logger.error(f"Recalculate risk scores error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to recalculate risk scores: {str(e)}"
        )


@router.get("/debug/firebase")
async def debug_firebase():
    """Debug Firebase configuration"""
    try:
        from ..core.config import settings
        
        config = {
            "firebase_configured": bool(
                settings.firebase_project_id and 
                settings.firebase_private_key and 
                settings.firebase_client_email
            ),
            "project_id": settings.firebase_project_id,
            "client_email": settings.firebase_client_email,
            "private_key_configured": bool(settings.firebase_private_key),
            "environment": settings.environment
        }
        
        return config
        
    except Exception as e:
        logger.error(f"Debug Firebase error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Firebase debug info: {str(e)}"
        )


@router.get("/debug/vertex-ai")
async def debug_vertex_ai():
    """Debug Vertex AI configuration"""
    try:
        from ..core.config import settings
        
        config = {
            "vertex_ai_configured": bool(settings.google_cloud_project),
            "project": settings.google_cloud_project,
            "location": settings.vertex_ai_location,
            "model": settings.vertex_ai_model,
            "environment": settings.environment,
            "initialized": vertex_ai_client.initialized
        }
        
        return config
        
    except Exception as e:
        logger.error(f"Debug Vertex AI error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Vertex AI debug info: {str(e)}"
        )