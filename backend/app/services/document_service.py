"""Core document orchestration service executing the end-to-end processing pipeline."""

import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.models.document import ProcessedDocument
from backend.app.repositories.document_repository import DocumentRepository
from backend.app.schemas.document import DocumentProcessResponse, DocumentListItem
from backend.app.schemas.extraction import ProcessingMetadata
from backend.app.services.document_validation_service import DocumentValidationService
from backend.app.services.ocr_service import OCRService
from backend.app.services.extraction_service import ExtractionService
from backend.app.services.financial_validation_service import FinancialValidationService
from backend.app.utils.helpers import DocumentProcessingException


class DocumentService:
    """Orchestrates validation, OCR, AI extraction, financial reconciliation, and persistence."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = DocumentRepository(db)

    def process_document(
        self,
        filename: str,
        file_bytes: bytes,
        document_type: str
    ) -> DocumentProcessResponse:
        """
        Executes complete pipeline:
        Validation -> OCR -> Extraction -> Financial Validation -> Persistence -> Structured JSON.
        """
        start_time = time.time()
        logger.info(f"Beginning pipeline for document: '{filename}' (Type: '{document_type}')")

        # 1. Step 1: Input Validation
        validation_detail = DocumentValidationService.validate_file(filename, file_bytes)

        # Persist upload locally
        try:
            safe_name = f"{int(time.time())}_{os.path.basename(filename)}"
            save_path = os.path.join(settings.UPLOAD_DIR, safe_name)
            with open(save_path, "wb") as f:
                f.write(file_bytes)
        except Exception as file_err:
            logger.warning(f"Could not persist upload to disk: {file_err}")

        # 2. Step 2: Content Extraction / OCR
        page_records, page_images, ocr_used = OCRService.extract_document_content(
            filename, file_bytes, validation_detail.file_type
        )

        # 3. Step 3: AI-based Field & Table Extraction
        extracted_data, overall_confidence = ExtractionService.extract(
            document_type=document_type,
            page_records=page_records,
            page_images=page_images
        )

        # 4. Step 4: Financial Calculation Validation
        validation_summary = FinancialValidationService.validate(
            document_type=document_type,
            extracted_data=extracted_data
        )

        # 5. Step 5: Processing Status
        # PASS: required fields are extracted accurately and required validations pass
        # FAILED: document could not be processed, is invalid, corrupted or unsupported
        processing_status = "PASS" if validation_summary.overall_status == "PASS" else "FAILED"

        # 6. Step 6: Metadata & Telemetry
        processing_time_ms = int((time.time() - start_time) * 1000)
        processed_at_iso = datetime.now(timezone.utc).isoformat()

        processing_metadata = ProcessingMetadata(
            ocr_used=ocr_used,
            processed_at=processed_at_iso,
            processing_time_ms=processing_time_ms
        )

        # 7. Step 7: Persistence to Database
        db_doc = ProcessedDocument(
            document_name=filename,
            document_type=document_type,
            processing_status=processing_status,
            overall_confidence=overall_confidence,
            file_validation=validation_detail.model_dump(),
            extracted_data=extracted_data,
            validation_result=validation_summary.model_dump(),
            processing_metadata=processing_metadata.model_dump()
        )
        self.repo.save(db_doc)
        logger.info(f"Document '{filename}' processed and saved with ID {db_doc.id} (Status: {processing_status})")

        return DocumentProcessResponse(
            document_name=filename,
            document_type=document_type,
            processing_status=processing_status,
            overall_confidence=overall_confidence,
            file_validation=validation_detail,
            extracted_data=extracted_data,
            validation=validation_summary,
            processing_metadata=processing_metadata
        )

    def get_by_name(self, document_name: str) -> Optional[DocumentProcessResponse]:
        """Retrieves the latest structured result matching document_name."""
        doc = self.repo.get_latest_by_name(document_name)
        if not doc:
            return None
        return self._to_response_schema(doc)

    def get_by_id(self, doc_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves a document by its database primary key."""
        doc = self.repo.get_by_id(doc_id)
        if not doc:
            return None
        return self._to_response_dict(doc)

    def list_documents(
        self,
        skip: int = 0,
        limit: int = 100,
        document_type: Optional[str] = None
    ) -> List[DocumentListItem]:
        """Lists processed documents formatted for dashboard."""
        docs = self.repo.list_documents(skip=skip, limit=limit, document_type=document_type)
        items: List[DocumentListItem] = []
        for d in docs:
            f_val = d.file_validation or {}
            p_meta = d.processing_metadata or {}
            items.append(DocumentListItem(
                id=d.id,
                document_name=d.document_name,
                document_type=d.document_type,
                processing_status=d.processing_status,
                overall_confidence=d.overall_confidence,
                page_count=f_val.get("page_count", 1),
                ocr_used=p_meta.get("ocr_used", False),
                processed_at=p_meta.get("processed_at", str(d.created_at)),
                processing_time_ms=p_meta.get("processing_time_ms", 0)
            ))
        return items

    def _to_response_schema(self, doc: ProcessedDocument) -> DocumentProcessResponse:
        """Maps database record to DocumentProcessResponse schema."""
        return DocumentProcessResponse(
            document_name=doc.document_name,
            document_type=doc.document_type,
            processing_status=doc.processing_status,
            overall_confidence=doc.overall_confidence,
            file_validation=doc.file_validation,
            extracted_data=doc.extracted_data or {},
            validation=doc.validation_result or {"checks": [], "overall_status": doc.processing_status, "issues": []},
            processing_metadata=doc.processing_metadata or {
                "ocr_used": False,
                "processed_at": str(doc.created_at),
                "processing_time_ms": 0
            }
        )

    def _to_response_dict(self, doc: ProcessedDocument) -> Dict[str, Any]:
        """Maps database record to dictionary with primary id."""
        resp = self._to_response_schema(doc).model_dump()
        resp["id"] = doc.id
        return resp
