#!/usr/bin/env python3
"""
Quick setup script to create all missing files for Smart Aid & Budget backend.
Run with: python setup_project.py
"""

import os
import sys

# Define the project structure with file contents
PROJECT_STRUCTURE = {
    # Root files
    "requirements.txt": """fastapi==0.104.1
uvicorn[standard]==0.24.0
python-dotenv==1.0.0
sqlalchemy[asyncio]==2.0.23
asyncpg==0.29.0
alembic==1.12.1
psycopg2-binary==2.9.9
pydantic==2.5.0
pydantic-settings==2.1.0
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
firebase-admin==6.2.0
google-cloud-aiplatform==1.38.1
google-auth==2.23.4
google-cloud-logging==3.8.0
redis==5.0.1
httpx==0.25.1
requests==2.31.0
python-multipart==0.0.6
python-dateutil==2.8.2
pytz==2023.3.post1
email-validator==2.1.0
prometheus-fastapi-instrumentator==6.1.0
pytest==7.4.3
pytest-asyncio==0.21.1
pytest-cov==4.1.0""",
    
    ".env.example": """# App Configuration
APP_NAME="Smart Aid & Budget Backend"
ENVIRONMENT=development
DEBUG=True
API_V1_STR=/api/v1
SECRET_KEY=development-secret-key-change-in-production

# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/smartaid_db

# Firebase (optional for development)
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...
FIREBASE_CLIENT_EMAIL=firebase-adminsdk@project.iam.gserviceaccount.com

# Google Cloud (optional for development)
GOOGLE_CLOUD_PROJECT=your-project-id
VERTEX_AI_LOCATION=us-central1
VERTEX_AI_MODEL=gemini-1.5-pro

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600

# External APIs
SCHOLARSHIP_API_BASE_URL=https://api.example.com/scholarships/v1

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# Security
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60""",
    
    "Dockerfile": """FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    postgresql-client \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
  CMD curl -f http://localhost:8080/health || exit 1

# Run migrations and start app
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload"]""",
    
    "docker-compose.yml": """version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: smartaid_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  backend:
    build: .
    ports:
      - "8000:8080"
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:password@postgres:5432/smartaid_db
      REDIS_URL: redis://redis:6379/0
      ENVIRONMENT: development
      DEBUG: "True"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    volumes:
      - .:/app
    stdin_open: true
    tty: true

volumes:
  postgres_data:
  redis_data:""",
    
    # Alembic files
    "alembic/env.py": """from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.config import settings
from app.models.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the SQLAlchemy URL from settings
config.set_main_option("sqlalchemy.url", str(settings.database_url))

# add your model's MetaData object here
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()""",
    
    "alembic/script.py.mako": """\"\"\"${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

\"\"\"
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

def upgrade() -> None:
    ${upgrades if upgrades else "pass"}

def downgrade() -> None:
    ${downgrades if downgrades else "pass"}""",
    
    "alembic.ini": """[alembic]
script_location = alembic

[post_write_hooks]
# hooks = black
# black.type = console_scripts
# black.entrypoint = black
# black.options = -l 79 REVISION_SCRIPT_FILENAME

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S

sqlalchemy.url = postgresql+asyncpg://postgres:password@localhost:5432/smartaid_db""",
    
    # App package init
    "app/__init__.py": """# Smart Aid & Budget Backend""",
    
    # Core module
    "app/core/__init__.py": """# Core configuration and utilities""",
    
    "app/core/config.py": """from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, validator, Field
import secrets

class Settings(BaseSettings):
    app_name: str = "Smart Aid & Budget Backend"
    environment: str = "development"
    debug: bool = False
    api_v1_str: str = "/api/v1"
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    
    cors_origins: List[str] = Field(default=["http://localhost:3000"])
    
    database_url: Optional[PostgresDsn] = None
    
    firebase_project_id: Optional[str] = None
    firebase_private_key: Optional[str] = None
    firebase_client_email: Optional[str] = None
    
    google_cloud_project: Optional[str] = None
    vertex_ai_location: str = "us-central1"
    vertex_ai_model: str = "gemini-1.5-pro"
    
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600
    
    rate_limit_requests: int = 100
    rate_limit_period: int = 60
    
    scholarship_api_base_url: str = "https://api.example.com/scholarships/v1"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @validator("database_url", pre=True)
    def assemble_db_connection(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v
        return "postgresql+asyncpg://postgres:password@localhost:5432/smartaid_db"

settings = Settings()""",
    
    "app/core/security.py": """from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

logger = logging.getLogger(__name__)

class FirebaseAuth:
    def __init__(self):
        self.security = HTTPBearer(auto_error=False)
    
    async def __call__(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer())
    ) -> Dict[str, Any]:
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer token required",
            )
        
        # Mock authentication for development
        return {
            "uid": "mock_uid_123",
            "email": "student@example.com",
            "email_verified": True,
            "role": "student",
        }

get_current_user = FirebaseAuth()""",
    
    "app/core/database.py": """from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from .config import settings
import logging

logger = logging.getLogger(__name__)

engine = create_async_engine(
    str(settings.database_url),
    echo=settings.debug,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
    logger.info("Database tables created successfully")

async def check_db_connection() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False

async def close_db():
    await engine.dispose()
    logger.info("Database connections closed")""",
    
    "app/core/exceptions.py": """from fastapi import HTTPException, status
from typing import Any, Dict, Optional

class SmartAidException(HTTPException):
    def __init__(
        self,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        detail: Any = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)

class NotFoundError(SmartAidException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} not found",
        )

class ValidationError(SmartAidException):
    def __init__(self, detail: str = "Validation failed"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )

class ConflictError(SmartAidException):
    def __init__(self, detail: str = "Resource already exists"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )""",
    
    "app/core/dependencies.py": """from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from .database import get_db
from .security import get_current_user

# Re-export dependencies
__all__ = ["get_db", "get_current_user"]""",
    
    # API module
    "app/api/__init__.py": """# API endpoints""",
    
    "app/api/v1/__init__.py": """# API v1 endpoints""",
    
    "app/api/v1/router.py": """from fastapi import APIRouter
from . import auth

api_router = APIRouter()

api_router.include_router(auth.router)

@api_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Smart Aid & Budget API",
        "version": "1.0.0"
    }

@api_router.get("/")
async def root():
    return {
        "message": "Welcome to Smart Aid & Budget API",
        "version": "1.0.0",
        "documentation": "/docs",
        "endpoints": {
            "auth": "/api/v1/auth",
            "health": "/api/v1/health"
        }
    }""",
    
    "app/api/v1/auth.py": """from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from ...core.database import get_db
from ...core.security import get_current_user

router = APIRouter(prefix="/auth", tags=["authentication"])
logger = logging.getLogger(__name__)

@router.post("/login")
async def login():
    """Login endpoint (mock for development)"""
    return {
        "access_token": "mock_jwt_token",
        "token_type": "bearer",
        "expires_in": 3600,
        "user": {
            "id": "mock_user_id",
            "email": "student@example.com",
            "full_name": "Test Student",
            "role": "student"
        }
    }

@router.get("/me")
async def get_current_user_info(
    current_user: dict = Depends(get_current_user)
):
    """Get current user information"""
    return {
        "uid": current_user["uid"],
        "email": current_user["email"],
        "role": current_user["role"],
        "email_verified": current_user["email_verified"]
    }""",
    
    # Main app file
    "app/main.py": """from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from .core.config import settings
from .core.database import init_db, close_db
from .api.v1.router import api_router

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🚀 Starting Smart Aid & Budget Backend...")
    
    try:
        await init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Smart Aid & Budget Backend...")
    await close_db()

app = FastAPI(
    title="Smart Aid & Budget Backend API",
    description="Backend API for Smart Aid & Budget Platform",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_str)

@app.get("/")
async def root():
    return {
        "message": "Welcome to Smart Aid & Budget API",
        "version": "1.0.0",
        "health_check": "/api/v1/health",
        "environment": settings.environment
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Smart Aid & Budget API"
    }

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=settings.debug,
        log_level="info" if settings.environment == "production" else "debug"
    )""",
    
    # Empty init files for other directories
    "app/models/__init__.py": """# Database models""",
    "app/schemas/__init__.py": """# Pydantic schemas""",
    "app/services/__init__.py": """# Business logic services""",
    "app/integrations/__init__.py": """# External service integrations""",
    "app/utils/__init__.py": """# Utility functions""",
    "app/notifications/__init__.py": """# Notification handlers""",
    "app/ai/__init__.py": """# AI integration module""",
    
    # Scripts
    "scripts/__init__.py": """# Scripts package""",
    
    # Test init files
    "app/tests/__init__.py": """# Tests package""",
    "app/tests/test_api/__init__.py": """# API tests""",
    "app/tests/test_models/__init__.py": """# Model tests""",
    "app/tests/test_services/__init__.py": """# Service tests""",
    "app/tests/test_integrations/__init__.py": """# Integration tests""",
    
    # Simple test file
    "app/tests/test_basic.py": """import pytest
from fastapi.testclient import TestClient

from ..main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()""",
    
    # Docs
    "docs/API.md": """# Smart Aid & Budget API Documentation

## Base URL