from typing import Optional, List
from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, validator, Field


class Settings(BaseSettings):
    # App
    app_name: str = "Smart Aid & Budget"
    environment: str = "development"
    debug: bool = False
    api_v1_str: str = "/api/v1"
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
    scholarship_api_base_url: str = "https://api.scholarships.com/v1"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
    
    @validator("database_url", pre=True)
    def assemble_db_connection(cls, v: Optional[str]) -> Optional[str]:
        if isinstance(v, str):
            return v
        return "postgresql+asyncpg://smartaid:smartaid123@localhost:5432/smartaid_db"


settings = Settings()