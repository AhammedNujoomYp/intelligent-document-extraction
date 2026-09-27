"""REST API routes for Document Intelligence platform."""

from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.logging import logger
from backend.app.schemas.document import (
    DocumentListItem,
    DocumentProcessResponse,
    DocumentType,
    ErrorResponse
)
from backend.app.services.document_service import DocumentService
from backend.app.utils.helpers import DocumentProcessingException

router = APIRouter(tags=["Documents"])


@router.get(
    "/health",
    summary="Health Check",
    description="Returns service health status for deployment monitoring."
)
def health_check():
    """Health endpoint returning service uptime and status."""
    return {
        "status": "healthy",
        "service": "Intelligent Document Extraction, Validation & API Platform",
        "version": "1.0.0"
    }


@router.post(
    "/documents/process",
    response_model=DocumentProcessResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid input or validation error"},
        422: {"model": ErrorResponse, "description": "Unprocessable entity"}
    },
    summary="Upload and process a financial document",
    description="Accepts a PDF, JPG, or PNG document (up to 3 pages) along with document_type metadata."
)
async def process_document(
    file: UploadFile = File(..., description="Document file (PDF, JPG, or PNG)"),
    document_type: str = Form(..., description="Document category: invoice, balance_sheet, profit_and_loss, cash_flow_statement"),
    db: Session = Depends(get_db)
):
    """Processes document through validation, extraction, financial calculation, and persistence."""
    logger.info(f"Incoming upload request: '{file.filename}', document_type: '{document_type}'")

    valid_types = {t.value for t in DocumentType}
    if document_type.lower() not in valid_types:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": "INVALID_DOCUMENT_TYPE",
                    "message": f"Invalid document_type '{document_type}'. Supported types: {', '.join(valid_types)}"
                }
            }
        )

    try:
        file_bytes = await file.read()
        service = DocumentService(db)
        response = service.process_document(
            filename=file.filename or "unknown_file",
            file_bytes=file_bytes,
            document_type=document_type.lower()
        )
        return response

    except DocumentProcessingException as dpe:
        logger.warning(f"Document processing exception: [{dpe.code}] {dpe.message}")
        return JSONResponse(
            status_code=dpe.status_code,
            content={"error": {"code": dpe.code, "message": dpe.message}}
        )
    except Exception as e:
        logger.error(f"Unexpected processing error for '{file.filename}': {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred while processing the document."
                }
            }
        )


@router.get(
    "/documents/{document_name}",
    response_model=DocumentProcessResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Retrieve latest result by document name",
    description="Fetches the most recent structured extraction and validation results using the document filename."
)
def get_document_by_name(
    document_name: str,
    db: Session = Depends(get_db)
):
    """Retrieve the latest structured result using document/file name."""
    service = DocumentService(db)
    result = service.get_by_name(document_name)
    if not result:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": "DOCUMENT_NOT_FOUND",
                    "message": f"No document found matching name '{document_name}'."
                }
            }
        )
    return result


@router.get(
    "/documents",
    response_model=List[DocumentListItem],
    summary="List all processed documents",
    description="Returns a paginated list of all processed documents for the dashboard."
)
def list_documents(
    skip: int = 0,
    limit: int = 100,
    document_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Lists processed documents with metadata, status, confidence, and timestamps."""
    service = DocumentService(db)
    return service.list_documents(skip=skip, limit=limit, document_type=document_type)
