"""API Integration Tests using FastAPI TestClient."""

import io
import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject, DictionaryObject

from backend.app.main import app

client = TestClient(app)


def create_sample_invoice_pdf() -> bytes:
    """Creates a sample invoice PDF in-memory using pypdf."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)

    lines = [
        "Acme Software Inc.",
        "INVOICE",
        "Invoice Number: INV-2026-001",
        "Date: 2026-09-01",
        "Bill To: TechCorp Global",
        "Subtotal: 1000.00",
        "Tax: 100.00",
        "Discount: 0.00",
        "Total Amount: 1100.00"
    ]

    stream = DecodedStreamObject()
    content = "BT /F1 12 Tf 50 700 Td (" + ") Tj T* (".join(lines) + ") Tj ET"
    stream.set_data(content.encode("latin1"))
    page[NameObject("/Contents")] = stream

    font_dict = DictionaryObject({
        NameObject("/F1"): DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica")
        })
    })
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): font_dict})

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_health_check_endpoint():
    """Verify mandatory health check endpoint."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data


def test_process_document_success():
    """Verify POST /api/v1/documents/process returns Section 5.2 mandatory structured response."""
    pdf_bytes = create_sample_invoice_pdf()
    files = {"file": ("invoice_sample_01.pdf", pdf_bytes, "application/pdf")}
    data = {"document_type": "invoice"}

    response = client.post("/api/v1/documents/process", files=files, data=data)
    assert response.status_code == 200
    res_json = response.json()

    # Section 5.2 Mandatory Structured Response Assertions
    assert res_json["document_name"] == "invoice_sample_01.pdf"
    assert res_json["document_type"] == "invoice"
    assert res_json["processing_status"] in ("PASS", "FAILED")
    assert "overall_confidence" in res_json

    # File validation
    assert "file_validation" in res_json
    assert res_json["file_validation"]["status"] == "PASS"
    assert res_json["file_validation"]["is_supported"] is True

    # Extracted data
    assert "extracted_data" in res_json
    assert res_json["extracted_data"]["invoice_number"]["value"] == "INV-2026-001"

    # Validation
    assert "validation" in res_json
    assert "checks" in res_json["validation"]
    assert "overall_status" in res_json["validation"]

    # Processing metadata
    assert "processing_metadata" in res_json
    assert "ocr_used" in res_json["processing_metadata"]
    assert "processing_time_ms" in res_json["processing_metadata"]


def test_process_unsupported_file_error():
    """Verify Section 5.3 Error response for unsupported file format."""
    files = {"file": ("unsupported_data.txt", b"plain text data", "text/plain")}
    data = {"document_type": "invoice"}

    response = client.post("/api/v1/documents/process", files=files, data=data)
    assert response.status_code == 400
    res_json = response.json()

    assert "error" in res_json
    assert res_json["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
    assert "Only PDF / JPG / PNG" in res_json["error"]["message"]


def test_get_document_by_name():
    """Verify GET /api/v1/documents/{document_name} returns latest structured result."""
    pdf_bytes = create_sample_invoice_pdf()
    doc_name = "unique_invoice_test.pdf"
    files = {"file": (doc_name, pdf_bytes, "application/pdf")}
    data = {"document_type": "invoice"}

    post_resp = client.post("/api/v1/documents/process", files=files, data=data)
    assert post_resp.status_code == 200

    # Retrieve by name
    get_resp = client.get(f"/api/v1/documents/{doc_name}")
    assert get_resp.status_code == 200
    assert get_resp.json()["document_name"] == doc_name


def test_get_document_by_name_not_found():
    """Verify 404 response when document name does not exist."""
    response = client.get("/api/v1/documents/non_existent_document.pdf")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_list_documents_endpoint():
    """Verify GET /api/v1/documents returns list of records."""
    response = client.get("/api/v1/documents")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    if items:
        assert "document_name" in items[0]
        assert "processing_status" in items[0]
