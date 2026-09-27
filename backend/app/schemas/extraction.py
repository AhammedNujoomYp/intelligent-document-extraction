"""Pydantic schemas for data extraction and financial validations."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """Source evidence grounding an extracted value."""
    source_text: str = Field(..., description="Exact snippet from source document")
    page_number: int = Field(..., description="Page number where snippet appears (1-indexed)")


class FieldValue(BaseModel):
    """Encapsulates an extracted value with optional confidence and evidence."""
    value: Any = Field(..., description="Extracted scalar or string value, or null if missing")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score 0.0 - 1.0")
    page_number: Optional[int] = Field(None, description="Page number (1-indexed)")
    evidence: Optional[Evidence] = Field(None, description="Evidence snippet and page")


class LineItem(BaseModel):
    """Structured line item from an invoice or financial statement."""
    description: str
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    amount: Optional[float] = None


class ValidationCheck(BaseModel):
    """Individual financial calculation validation result."""
    name: str = Field(..., description="Validation check name")
    formula: str = Field(..., description="Mathematical relationship or formula tested")
    operands: Dict[str, Any] = Field(default_factory=dict, description="Input values used in check")
    calculated_value: Optional[float] = Field(None, description="Value computed by formula")
    reported_value: Optional[float] = Field(None, description="Value reported on document")
    variance: Optional[float] = Field(None, description="Absolute difference between computed and reported")
    status: str = Field(..., description="Status: PASS, FAIL, or NOT_APPLICABLE")


class ValidationSummary(BaseModel):
    """Aggregate validation result container."""
    checks: List[ValidationCheck] = Field(default_factory=list)
    overall_status: str = Field("PASS", description="PASS or FAIL")
    issues: List[str] = Field(default_factory=list)


class ProcessingMetadata(BaseModel):
    """Execution telemetry and runtime metadata."""
    ocr_used: bool = False
    processed_at: str
    processing_time_ms: int
