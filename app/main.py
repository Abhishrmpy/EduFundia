from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time
from prometheus_fastapi_instrumentator import Instrumentator

from .core.config import settings
from .core.database import init_db, close_db
from .core.exceptions import (
    SmartAidException, AuthenticationError, AuthorizationError,
    NotFoundError, ValidationError, ConflictError, RateLimitError,
    ExternalServiceError
)
from .api.v1.router import api_router
from .api.internal import router as internal_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.environment == "production" else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events"""
    # Startup
    logger.info("🚀 Starting Smart Aid & Budget Backend...")
    logger.info(f"📁 Environment: {settings.environment}")
    logger.info(f"🔧 Debug mode: {settings.debug}")
    
    # Initialize database
    try:
        await init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    
    # Initialize monitoring
    if settings.environment == "production":
        Instrumentator().instrument(app).expose(app)
        logger.info("📊 Monitoring instrumentation enabled")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Smart Aid & Budget Backend...")
    await close_db()
    logger.info("✅ Database connections closed")


# Create FastAPI app
app = FastAPI(
    title="Smart Aid & Budget Backend API",
    description="Backend API for Smart Aid & Budget - Financial Stress & Bursaries Platform for Students",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.debug else [
        "localhost",
        "127.0.0.1",
        ".smartaid.com",
        ".vercel.app",
        ".onrender.com"
    ]
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

# Add request timing middleware
@app.middleware("http")
async def add_process_time_header(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Exception handlers
@app.exception_handler(SmartAidException)
async def smart_aid_exception_handler(request, exc: SmartAidException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "code": exc.status_code
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "code": exc.status_code
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": "Internal server error",
            "code": status.HTTP_500_INTERNAL_SERVER_ERROR
        }
    )

# Include routers
app.include_router(api_router, prefix=settings.api_v1_str)
app.include_router(internal_router, prefix="/internal")

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Smart Aid & Budget API",
        "version": "1.0.0",
        "documentation": "/docs" if settings.debug else None,
        "health_check": "/api/v1/health",
        "internal_health": "/internal/health",
        "environment": settings.environment
    }


@app.get("/favicon.ico")
async def favicon():
    """Favicon endpoint"""
    from fastapi.responses import FileResponse
    import os
    favicon_path = os.path.join(os.path.dirname(__file__), "static", "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    return {"message": "No favicon"}


# Health check endpoint
@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {
        "status": "healthy",
        "service": "Smart Aid & Budget API",
        "timestamp": time.time()
    }


# Main entry point
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.debug,
        log_level="info" if settings.environment == "production" else "debug"
    )