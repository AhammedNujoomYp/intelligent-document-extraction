"""Tests for Document Validation and Financial Validation Services."""

import io
import pytest
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject, DictionaryObject

from backend.app.services.document_validation_service import DocumentValidationService
from backend.app.services.financial_validation_service import FinancialValidationService
from backend.app.utils.helpers import DocumentProcessingException, parse_numeric


def create_dummy_pdf(num_pages: int, lines: list = None) -> bytes:
    """Helper creating an in-memory PDF with specified number of pages and text."""
    if lines is None:
        lines = ["Sample test document content."]
    writer = PdfWriter()
    for _ in range(num_pages):
        page = writer.add_blank_page(width=612, height=792)
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


def create_dummy_image(format="PNG") -> bytes:
    """Helper creating an in-memory test image."""
    img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


# ------------------------------------------------------------------------------
# 1. FILE INPUT VALIDATION TESTS
# ------------------------------------------------------------------------------
def test_validate_valid_pdf():
    pdf_bytes = create_dummy_pdf(2)
    val = DocumentValidationService.validate_file("test_doc.pdf", pdf_bytes)
    assert val.is_supported is True
    assert val.is_readable is True
    assert val.page_count == 2
    assert val.status == "PASS"


def test_validate_valid_image():
    img_bytes = create_dummy_image("JPEG")
    val = DocumentValidationService.validate_file("receipt.jpg", img_bytes)
    assert val.is_supported is True
    assert val.is_readable is True
    assert val.page_count == 1
    assert val.status == "PASS"


def test_reject_empty_file():
    with pytest.raises(DocumentProcessingException) as exc_info:
        DocumentValidationService.validate_file("empty.pdf", b"")
    assert exc_info.value.code == "EMPTY_FILE"


def test_reject_unsupported_file_type():
    with pytest.raises(DocumentProcessingException) as exc_info:
        DocumentValidationService.validate_file("test.docx", b"PK\x03\x04randomworddata")
    assert exc_info.value.code == "UNSUPPORTED_FILE_TYPE"


def test_reject_exceeding_page_limit():
    pdf_bytes = create_dummy_pdf(5)  # Max allowed is 3
    with pytest.raises(DocumentProcessingException) as exc_info:
        DocumentValidationService.validate_file("long_doc.pdf", pdf_bytes)
    assert exc_info.value.code == "EXCEEDS_PAGE_LIMIT"


def test_reject_corrupted_file():
    with pytest.raises(DocumentProcessingException) as exc_info:
        DocumentValidationService.validate_file("corrupt.pdf", b"%PDF-1.4 completely broken garbage")
    assert exc_info.value.code == "CORRUPTED_PDF"


# ------------------------------------------------------------------------------
# 2. NUMERICAL PARSER TESTS
# ------------------------------------------------------------------------------
def test_parse_numeric_formats():
    assert parse_numeric("$12,500.00") == 12500.00
    assert parse_numeric("USD 1,234.50") == 1234.50
    assert parse_numeric("(45,000)") == -45000.00
    assert parse_numeric("[1,250.75]") == -1250.75
    assert parse_numeric("-500.20") == -500.20
    assert parse_numeric("1.234,56") == 1234.56
    assert parse_numeric(None) is None
    assert parse_numeric("N/A") is None


# ------------------------------------------------------------------------------
# 3. FINANCIAL CALCULATION VALIDATION TESTS
# ------------------------------------------------------------------------------
def test_invoice_validation_pass():
    data = {
        "subtotal": 1000.00,
        "tax_amount": 100.00,
        "discount": 50.00,
        "total_amount": 1050.00,
        "line_items": [
            {"description": "Item 1", "quantity": 2.0, "unit_price": 500.0, "amount": 1000.0}
        ]
    }
    summary = FinancialValidationService.validate("invoice", data)
    assert summary.overall_status == "PASS"
    assert len(summary.checks) == 3
    assert all(c.status == "PASS" for c in summary.checks)


def test_invoice_validation_failure():
    # Wrong total amount triggers FAIL
    data = {
        "subtotal": 1000.00,
        "tax_amount": 100.00,
        "discount": 0.00,
        "total_amount": 1500.00,  # Expected 1100.00
    }
    summary = FinancialValidationService.validate("invoice", data)
    assert summary.overall_status == "FAIL"
    total_check = next(c for c in summary.checks if c.name == "invoice_total_check")
    assert total_check.status == "FAIL"
    assert total_check.variance == 400.00
    assert len(summary.issues) > 0


def test_balance_sheet_validation():
    data = {
        "total_assets": 500000.00,
        "total_capital_and_liabilities": 500000.00,
        "asset_components": [{"name": "Cash", "value": 500000.00}]
    }
    summary = FinancialValidationService.validate("balance_sheet", data)
    assert summary.overall_status == "PASS"


def test_pnl_validation():
    data = {
        "interest_earned": 300000.00,
        "other_income": 20000.00,
        "total_income": 320000.00,
        "interest_expended": 150000.00,
        "operating_expenses": 50000.00,
        "provisions_and_contingencies": 0.00,
        "total_expenditure": 200000.00,
        "profit_before_minority_interest": 120000.00,
        "minority_interest": 10000.00,
        "consolidated_net_profit": 110000.00
    }
    summary = FinancialValidationService.validate("profit_and_loss", data)
    assert summary.overall_status == "PASS"


def test_cash_flow_validation_with_negative_values():
    data = {
        "operating_cash_flow": 100000.00,
        "investing_cash_flow": -30000.00,
        "financing_cash_flow": -20000.00,
        "fx_adjustment": 0.00,
        "net_change_in_cash": 50000.00,
        "opening_cash": 20000.00,
        "closing_cash": 70000.00
    }
    summary = FinancialValidationService.validate("cash_flow_statement", data)
    assert summary.overall_status == "PASS"


def test_missing_field_returns_not_applicable():
    data = {
        "total_amount": 1000.00
        # subtotal and tax_amount omitted
    }
    summary = FinancialValidationService.validate("invoice", data)
    check = next(c for c in summary.checks if c.name == "invoice_total_check")
    assert check.status == "NOT_APPLICABLE"
