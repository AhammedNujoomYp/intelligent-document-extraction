"""OCR and text extraction service supporting native PDF extraction and OCR."""

import io
from typing import Dict, List, Tuple, Any
from PIL import Image

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

try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except ImportError:
    PYTESSERACT_AVAILABLE = False

from backend.app.core.logging import logger


class OCRService:
    """Extracts text and page images from native PDFs, scanned PDFs, and image files."""

    @staticmethod
    def extract_document_content(
        filename: str,
        file_bytes: bytes,
        mime_type: str
    ) -> Tuple[List[Dict[str, Any]], List[bytes], bool]:
        """
        Extracts textual content and images per page.
        Returns:
            - page_records: List[{"page_number": int, "text": str}]
            - page_images: List[bytes]
            - ocr_used: bool
        """
        logger.info(f"Extracting content from '{filename}' (MIME: {mime_type})")
        page_records: List[Dict[str, Any]] = []
        page_images: List[bytes] = []
        ocr_used = False

        if mime_type == "application/pdf":
            if PYPDF_AVAILABLE:
                stream = io.BytesIO(file_bytes)
                reader = PdfReader(stream)
                for p_num, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    if len(text.strip()) < 30:
                        ocr_used = True
                    page_records.append({
                        "page_number": p_num + 1,
                        "text": text.strip()
                    })
            elif MUPDF_AVAILABLE:
                pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
                for p_num in range(pdf_doc.page_count):
                    page = pdf_doc.load_page(p_num)
                    page_text = page.get_text("text").strip()
                    pix = page.get_pixmap(dpi=150)
                    img_bytes = pix.tobytes("png")
                    page_images.append(img_bytes)
                    if len(page_text) < 30:
                        ocr_used = True
                    page_records.append({
                        "page_number": p_num + 1,
                        "text": page_text
                    })
                pdf_doc.close()

        else:
            # JPG or PNG image document
            ocr_used = True
            page_images.append(file_bytes)
            extracted_text = ""

            if PYTESSERACT_AVAILABLE:
                try:
                    pil_img = Image.open(io.BytesIO(file_bytes))
                    extracted_text = pytesseract.image_to_string(pil_img).strip()
                except Exception as ocr_err:
                    logger.debug(f"Tesseract OCR fallback skipped: {ocr_err}")

            page_records.append({
                "page_number": 1,
                "text": extracted_text
            })

        logger.info(f"Content extraction completed for '{filename}'. Total pages: {len(page_records)}, OCR used: {ocr_used}")
        return page_records, page_images, ocr_used
