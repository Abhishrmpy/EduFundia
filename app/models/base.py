from sqlalchemy import Column, DateTime, func, Boolean
from sqlalchemy.orm import declared_attr, declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid


class BaseModel:
    """Base model with common fields"""

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower() + 's'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    def to_dict(self):
        """Convert model to dictionary"""
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


# Create a declarative base class that includes the common fields
Base = declarative_base(cls=BaseModel)

__all__ = ["Base", "BaseModel"]