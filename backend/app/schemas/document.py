"""Pydantic schemas for Document API requests and responses."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.app.schemas.extraction import ValidationSummary, ProcessingMetadata


class DocumentType(str, Enum):
    """Supported document types in scope."""
    INVOICE = "invoice"
    BALANCE_SHEET = "balance_sheet"
    PROFIT_AND_LOSS = "profit_and_loss"
    CASH_FLOW_STATEMENT = "cash_flow_statement"


class FileValidationDetail(BaseModel):
    """File integrity and format validation block."""
    file_type: str = Field(..., description="Detected MIME type")
    is_supported: bool = Field(..., description="Whether file format is supported")
    is_readable: bool = Field(..., description="Whether document can be read/parsed")
    page_count: int = Field(..., description="Total pages in document")
    status: str = Field(..., description="Validation status: PASS or FAILED")


class DocumentProcessResponse(BaseModel):
    """Mandatory structured response format as specified in Section 5.2."""
    document_name: str
    document_type: str
    processing_status: str = Field("PASS", description="PASS or FAILED")
    overall_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    file_validation: FileValidationDetail
    extracted_data: Dict[str, Any]
    validation: ValidationSummary
    processing_metadata: ProcessingMetadata


class DocumentListItem(BaseModel):
    """Summary item returned in document list API for dashboard."""
    id: int
    document_name: str
    document_type: str
    processing_status: str
    overall_confidence: Optional[float] = None
    page_count: int
    ocr_used: bool
    processed_at: str
    processing_time_ms: int


class ErrorDetail(BaseModel):
    """Error object containing code and message."""
    code: str
    message: str


class ErrorResponse(BaseModel):
    """Mandatory structured error response format as specified in Section 5.3."""
    error: ErrorDetail
