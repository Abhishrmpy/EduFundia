from fastapi import APIRouter
from . import auth, students, expenses, budget, scholarships, notifications, payments

api_router = APIRouter()

# Include all API routers
api_router.include_router(auth.router)
api_router.include_router(students.router)
api_router.include_router(expenses.router)
api_router.include_router(budget.router)
api_router.include_router(scholarships.router)
api_router.include_router(notifications.router)
api_router.include_router(payments.router)

# Health check endpoint
@api_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Smart Aid & Budget API",
        "version": "1.0.0"
    }


# Root endpoint
@api_router.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Welcome to Smart Aid & Budget API",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "auth": "/api/v1/auth",
            "students": "/api/v1/students",
            "expenses": "/api/v1/expenses",
            "budgets": "/api/v1/budgets",
            "scholarships": "/api/v1/scholarships",
            "notifications": "/api/v1/notifications",
            "payments": "/api/v1/payments"
        }
    }