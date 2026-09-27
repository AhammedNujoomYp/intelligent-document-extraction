"""Document validation service for file integrity, page count, and format control."""

import io
from PIL import Image

# Import pypdf or PyMuPDF safely
try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    import fitz
    MUPDF_AVAILABLE = True
except (ImportError, Exception):
    MUPDF_AVAILABLE = False

from backend.app.core.config import settings
from backend.app.core.logging import logger
from backend.app.schemas.document import FileValidationDetail
from backend.app.utils.helpers import DocumentProcessingException, detect_file_type


class DocumentValidationService:
    """Validates uploaded documents prior to extraction."""

    @staticmethod
    def validate_file(filename: str, file_bytes: bytes) -> FileValidationDetail:
        """
        Validates file format, page limit, and readability.
        Raises DocumentProcessingException on failure.
        """
        logger.info(f"Validating document: {filename} ({len(file_bytes)} bytes)")

        # 1. Empty file check
        if not file_bytes or len(file_bytes) == 0:
            logger.warning(f"File validation failed: Empty file '{filename}'")
            raise DocumentProcessingException(
                code="EMPTY_FILE",
                message="The uploaded file is empty.",
                status_code=400
            )

        # 2. File size limit
        if len(file_bytes) > settings.MAX_FILE_SIZE_BYTES:
            logger.warning(f"File validation failed: Exceeded max file size for '{filename}'")
            raise DocumentProcessingException(
                code="FILE_TOO_LARGE",
                message=f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
                status_code=400
            )

        # 3. Format / MIME Type support check
        mime_type, is_supported = detect_file_type(filename, file_bytes)
        if not is_supported:
            logger.warning(f"File validation failed: Unsupported format '{mime_type}' for '{filename}'")
            raise DocumentProcessingException(
                code="UNSUPPORTED_FILE_TYPE",
                message="Only PDF / JPG / PNG documents are supported.",
                status_code=400
            )

        page_count = 1
        is_readable = False

        # 4. Check readability & page count
        if mime_type == "application/pdf":
            try:
                if PYPDF_AVAILABLE:
                    stream = io.BytesIO(file_bytes)
                    reader = PdfReader(stream)
                    if reader.is_encrypted:
                        raise DocumentProcessingException(
                            code="ENCRYPTED_PDF",
                            message="Encrypted or password-protected PDF files are not supported.",
                            status_code=400
                        )
                    page_count = len(reader.pages)
                    if page_count < 1:
                        raise DocumentProcessingException(
                            code="EMPTY_DOCUMENT",
                            message="The PDF document contains no pages.",
                            status_code=400
                        )
                    # Verify first page can be read
                    _ = reader.pages[0].extract_text()
                    is_readable = True
                elif MUPDF_AVAILABLE:
                    pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
                    if pdf_doc.is_encrypted:
                        raise DocumentProcessingException(
                            code="ENCRYPTED_PDF",
                            message="Encrypted or password-protected PDF files are not supported.",
                            status_code=400
                        )
                    page_count = pdf_doc.page_count
                    if page_count < 1:
                        raise DocumentProcessingException(
                            code="EMPTY_DOCUMENT",
                            message="The PDF document contains no pages.",
                            status_code=400
                        )
                    for p in range(page_count):
                        _ = pdf_doc.load_page(p)
                    is_readable = True
                    pdf_doc.close()
                else:
                    raise DocumentProcessingException(
                        code="INTERNAL_ERROR",
                        message="No PDF reader backend installed.",
                        status_code=500
                    )
            except DocumentProcessingException:
                raise
            except Exception as e:
                logger.error(f"Failed to read PDF '{filename}': {e}")
                raise DocumentProcessingException(
                    code="CORRUPTED_PDF",
                    message="The uploaded PDF file is corrupted or unreadable.",
                    status_code=400
                )
        else:
            # Image validation (JPG / PNG)
            try:
                img = Image.open(io.BytesIO(file_bytes))
                img.verify()
                # Re-open to verify readable dimensions
                img = Image.open(io.BytesIO(file_bytes))
                _ = img.size
                page_count = 1
                is_readable = True
            except Exception as e:
                logger.error(f"Failed to read image '{filename}': {e}")
                raise DocumentProcessingException(
                    code="CORRUPTED_IMAGE",
                    message="The uploaded image file is corrupted or unreadable.",
                    status_code=400
                )

        # 5. Page count limit check (max 3 pages)
        if page_count > settings.MAX_PAGE_LIMIT:
            logger.warning(f"File validation failed: Page count {page_count} exceeds limit {settings.MAX_PAGE_LIMIT}")
            raise DocumentProcessingException(
                code="EXCEEDS_PAGE_LIMIT",
                message=f"Document contains {page_count} pages. Maximum allowed is {settings.MAX_PAGE_LIMIT} pages.",
                status_code=400
            )

        logger.info(f"File validation passed: {filename} (Type: {mime_type}, Pages: {page_count})")
        return FileValidationDetail(
            file_type=mime_type,
            is_supported=True,
            is_readable=is_readable,
            page_count=page_count,
            status="PASS"
        )
