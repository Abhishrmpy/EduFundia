from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, validator, Field
import secrets


class Settings(BaseSettings):
    # App
    app_name: str = "Smart Aid & Budget Backend"
    environment: str = "development"
    debug: bool = False
    api_v1_str: str = "/api/v1"
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    
    # CORS
    cors_origins: List[str] = Field(default=["http://localhost:3000"])
    
    # Database
    database_url: Optional[PostgresDsn] = None
    database_pool_size: int = 20
    database_max_overflow: int = 40
    
    # Firebase
    firebase_project_id: Optional[str] = None
    firebase_private_key: Optional[str] = None
    firebase_client_email: Optional[str] = None
    
    # Google Cloud
    google_cloud_project: Optional[str] = None
    vertex_ai_location: str = "us-central1"
    vertex_ai_model: str = "gemini-1.5-pro"
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600
    
    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_period: int = 60
    
    # External APIs
    scholarship_api_base_url: str = "https://api.example.com/scholarships/v1"
    
    # File Upload
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: List[str] = Field(default=["image/jpeg", "image/png", "application/pdf"])
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @validator("database_url", pre=True)
    def assemble_db_connection(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v
        return "postgresql+asyncpg://postgres:password@localhost:5432/smartaid_db"
    
    @validator("firebase_private_key", pre=True)
    def validate_firebase_key(cls, v: Optional[str]) -> Optional[str]:
        if v and "\\n" in v:
            return v.replace("\\n", "\n")
        return v


settings = Settings()