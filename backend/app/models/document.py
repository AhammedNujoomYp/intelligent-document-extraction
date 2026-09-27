"""SQLAlchemy model for Processed Documents."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from backend.app.core.database import Base


def utc_now():
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


class ProcessedDocument(Base):
    """Stores metadata, extracted data, and validation results of documents."""
    __tablename__ = "processed_documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    document_name = Column(String(255), index=True, nullable=False)
    document_type = Column(String(50), index=True, nullable=False)
    processing_status = Column(String(20), index=True, nullable=False, default="FAILED")
    overall_confidence = Column(Float, nullable=True)
    
    # JSON-encoded payloads
    file_validation = Column(JSON, nullable=False)
    extracted_data = Column(JSON, nullable=True)
    validation_result = Column(JSON, nullable=True)
    processing_metadata = Column(JSON, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, index=True)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def __repr__(self) -> str:
        return f"<ProcessedDocument(id={self.id}, name='{self.document_name}', type='{self.document_type}', status='{self.processing_status}')>"
