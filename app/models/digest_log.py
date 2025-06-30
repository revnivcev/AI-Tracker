from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from .database import Base


class DigestLog(Base):
    __tablename__ = "digest_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    queue_key = Column(String, nullable=False)
    digest_text = Column(Text, nullable=True)
    issues_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 