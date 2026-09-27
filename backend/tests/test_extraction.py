"""Tests for Document Text/OCR and Field Extraction Services."""

from backend.app.services.extraction_service import ExtractionService


def test_invoice_extraction():
    sample_text = """
    ABC Solutions Inc.
    123 Tech Park, Suite 400
    
    INVOICE
    Invoice Number: INV-9901
    Date: 2026-08-15
    Bill To: Global Logistics LLC
    
    Description                  Qty    Unit Price    Total
    Cloud Migration Consulting     2     2000.00     4000.00
    Security Audit                 1     1000.00     1000.00
    
    Subtotal: $5,000.00
    Tax: $250.00
    Discount: $0.00
    Total Amount: $5,250.00
    """
    page_records = [{"page_number": 1, "text": sample_text}]
    extracted_data, conf = ExtractionService.extract("invoice", page_records, [])

    assert extracted_data["invoice_number"]["value"] == "INV-9901"
    assert extracted_data["subtotal"]["value"] == 5000.00
    assert extracted_data["tax_amount"]["value"] == 250.00
    assert extracted_data["total_amount"]["value"] == 5250.00
    assert len(extracted_data["line_items"]) >= 1
    assert conf > 0.80


def test_balance_sheet_extraction():
    sample_text = """
    BALANCE SHEET as of Dec 31, 2025
    Entity: Pinnacle Corporation
    
    Current Assets: $1,000,000
    Non-Current Assets: $2,000,000
    Total Assets: $3,000,000
    
    Current Liabilities: $500,000
    Non-Current Liabilities: $500,000
    Total Liabilities: $1,000,000
    Total Stockholders' Equity: $2,000,000
    Total Capital & Liabilities: $3,000,000
    """
    page_records = [{"page_number": 1, "text": sample_text}]
    extracted_data, conf = ExtractionService.extract("balance_sheet", page_records, [])

    assert extracted_data["total_assets"]["value"] == 3000000.00
    assert extracted_data["total_liabilities"]["value"] == 1000000.00
    assert extracted_data["total_equity"]["value"] == 2000000.00
    assert conf > 0.80


def test_pnl_extraction():
    sample_text = """
    STATEMENT OF PROFIT AND LOSS
    Interest Earned: $500,000
    Other Income: $50,000
    Total Income: $550,000
    
    Interest Expended: $200,000
    Operating Expenses: $100,000
    Provisions and Contingencies: $25,000
    Total Expenditure: $325,000
    """
    page_records = [{"page_number": 1, "text": sample_text}]
    extracted_data, conf = ExtractionService.extract("profit_and_loss", page_records, [])

    assert extracted_data["interest_earned"]["value"] == 500000.00
    assert extracted_data["total_income"]["value"] == 550000.00
    assert extracted_data["total_expenditure"]["value"] == 325000.00


def test_cash_flow_extraction():
    sample_text = """
    CASH FLOW STATEMENT
    Operating Cash Flow: $150,000
    Investing Cash Flow: ($50,000)
    Financing Cash Flow: ($30,000)
    FX Adjustment: $0.00
    Net Increase in Cash: $70,000
    Opening Cash: $30,000
    Closing Cash: $100,000
    """
    page_records = [{"page_number": 1, "text": sample_text}]
    extracted_data, conf = ExtractionService.extract("cash_flow_statement", page_records, [])

    assert extracted_data["operating_cash_flow"]["value"] == 150000.00
    assert extracted_data["investing_cash_flow"]["value"] == -50000.00
    assert extracted_data["financing_cash_flow"]["value"] == -30000.00
    assert extracted_data["net_change_in_cash"]["value"] == 70000.00
    assert extracted_data["closing_cash"]["value"] == 100000.00
