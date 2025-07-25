from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.sql import func
from .base import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    config_key = Column(String(100), unique=True, nullable=False, comment="Configuration key")
    config_value = Column(Text, nullable=False, comment="Configuration value")
    description = Column(String(255), comment="Description of this configuration")

    # Define indexes
    __table_args__ = (
        Index("idx_config_key", "config_key"),
        Index("idx_updated_at", "updated_at"),
    )

    def __repr__(self):
        return f"<SystemConfig(id={self.id}, config_key={self.config_key}, updated_at={self.updated_at})>"
