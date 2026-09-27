<<<<<<< HEAD
# Intelligent Document Extraction, Validation & API Platform

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Tests Passing](https://img.shields.io/badge/pytest-23%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An end-to-end AI-powered document intelligence service that ingests financial documents (native or scanned PDFs, JPG, PNG up to 3 pages), extracts all visible key-value fields and tabular line items, performs strict mathematical and accounting reconciliations, persists records in a database, and provides both a deployed web dashboard and a REST API.

---

## 1. Solution Overview & Architecture

The platform separates responsibilities across dedicated layers to ensure reliability, security, maintainability, and testability.

### Architecture Diagram
The architecture is visually documented in [`docs/architecture.svg`](file:///docs/architecture.svg).

```
                      +---------------------------------------+
                      |         Client Layer                  |
                      |  - Web Dashboard (HTML/CSS/JS)        |
                      |  - REST API Clients (cURL/Postman)    |
                      |  - Swagger Documentation (/docs)      |
                      +-------------------+-------------------+
                                          |
                                          v  Multipart Upload
                      +-------------------+-------------------+
                      |      FastAPI Application Gateway      |
                      |  - CORS & Error Handling (Sec 5.3)    |
                      +-------------------+-------------------+
                                          |
                                          v
                      +-------------------+-------------------+
                      | 1. Document Validation Layer          |
                      |  - MIME & magic bytes verification   |
                      |  - File integrity & corruption test   |
                      |  - Enforce page count <= 3            |
                      +-------------------+-------------------+
                                          |
                                          v
                      +-------------------+-------------------+
                      | 2. OCR & Text Extraction Layer        |
                      |  - Native digital text (PyPDF/PyMuPDF)|
                      |  - Scanned image detection & OCR      |
                      +-------------------+-------------------+
                                          |
                                          v
                      +-------------------+-------------------+
                      | 3. AI Field & Table Extraction Layer  |
                      |  - Gemini 2.5/1.5 Flash Multimodal    |
                      |  - OpenAI GPT-4o / Heuristic Fallback |
                      |  - Evidence Grounding & Confidence    |
                      +-------------------+-------------------+
                                          |
                                          v
                      +-------------------+-------------------+
                      | 4. Financial Validation Engine        |
                      |  - Invoices: Line math, tax, total    |
                      |  - Balance Sheet: Assets = Cap & Liab |
                      |  - P&L: Income, Expense, Net Profit   |
                      |  - Cash Flow: Net change & closing    |
                      |  - Absolute tolerance <= 0.05         |
                      +-------------------+-------------------+
                                          |
                                          v
                      +-------------------+-------------------+
                      | 5. Persistence & Response Formatting  |
                      |  - SQLite / PostgreSQL via SQLAlchemy |
                      |  - Section 5.2 Structured JSON Schema |
                      |  - Dashboard Update & Auditing        |
                      +---------------------------------------+
```

---

## 2. Technology Stack & Design Decisions

| Component | Choice | Reason for Choice |
| :--- | :--- | :--- |
| **Backend Framework** | **FastAPI** | High-performance asynchronous execution, automatic OpenAPI/Swagger generation, strict Pydantic v2 data validation, and clean dependency injection. |
| **PDF Extraction** | **PyPDF & PyMuPDF** | Pure-python PyPDF fallback provides 100% portability across Windows and Linux Docker containers without missing DLL or runtime errors. |
| **Multimodal AI / OCR** | **Google Gemini Flash & OpenAI** | Gemini 2.5/1.5 Flash provides a free tier, handles native and scanned image PDFs with high visual accuracy, and outputs strict JSON Schema. |
| **Deterministic Fallback** | **RegEx / Heuristics Engine** | Built-in offline parser ensures zero external dependency failure during local development, CI/CD automated tests, or network isolation. |
| **Database & ORM** | **SQLAlchemy + SQLite / PostgreSQL** | Decoupled repository pattern; supports zero-config SQLite for lightweight deployment and PostgreSQL for production concurrency. |
| **Frontend UI** | **Jinja2 + HTML5/CSS3 + Vanilla JS** | Lightweight, modern responsive dashboard with zero build step (no Node/Webpack overhead), instant loading, and built-in syntax-highlighted raw JSON viewer. |
| **Automated Testing** | **Pytest** | Fast, comprehensive automated test suite covering unit validation, math checks, and end-to-end API flows. |

---

## 3. Local Setup Instructions

### Prerequisites
- Python 3.10+ (tested on Python 3.11)
- Git

### Step-by-Step Setup
1. **Clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/intelligent-document-extraction.git
   cd intelligent-document-extraction
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   *(Optionally add your `GEMINI_API_KEY` or `OPENAI_API_KEY` in `.env`. If left blank, the deterministic fallback extractor runs automatically!)*

5. **Run the Automated Test Suite:**
   ```bash
   python -m pytest backend/tests -v
   ```
   *(All 23 automated tests should pass in ~1 second).*

6. **Start the local server:**
   ```bash
   python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Access the application:**
   - **Frontend Dashboard:** [http://localhost:8000](http://localhost:8000)
   - **Interactive API Docs (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Health Endpoint:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

## 4. Environment Variables (`.env.example`)

| Variable | Description | Default |
| :--- | :--- | :--- |
| `PROJECT_NAME` | Name of the platform | `"Intelligent Document Extraction Platform"` |
| `VERSION` | API Version | `"1.0.0"` |
| `PORT` | Application server port | `8000` |
| `HOST` | Bind host | `"0.0.0.0"` |
| `DATABASE_URL` | SQLAlchemy database connection string | `"sqlite:///./documents.db"` |
| `UPLOAD_DIR` | Directory to save processed uploads | `"./uploads"` |
| `MAX_PAGE_LIMIT` | Maximum allowed document pages | `3` |
| `FINANCIAL_TOLERANCE` | Numerical variance threshold for checks | `0.05` |
| `GEMINI_API_KEY` | Optional Google Gemini API Key | `""` |
| `OPENAI_API_KEY` | Optional OpenAI API Key | `""` |

---

## 5. Deployment Information

| Target | Live Submission URL |
| :--- | :--- |
| **Frontend Dashboard** | `https://intelligent-document-extraction.onrender.com` |
| **Backend Base API** | `https://intelligent-document-extraction.onrender.com/api/v1` |
| **Swagger/OpenAPI** | `https://intelligent-document-extraction.onrender.com/docs` |
| **Health Endpoint** | `https://intelligent-document-extraction.onrender.com/api/v1/health` |
| **Public GitHub Repo** | `https://github.com/<your-username>/intelligent-document-extraction` |

### Cloud Deployment (Render / Railway / Koyeb)
A production-ready [`Dockerfile`](file:///Dockerfile) and [`render.yaml`](file:///render.yaml) blueprint are included in the repository for zero-downtime 1-click deployment.

---

## 6. API Request Examples

### 1. Process Document (POST Multipart)
```bash
curl -X POST "http://localhost:8000/api/v1/documents/process" \
  -F "file=@sample_invoice.pdf" \
  -F "document_type=invoice"
```

**Response (Section 5.2 Schema):**
```json
{
  "document_name": "sample_invoice.pdf",
  "document_type": "invoice",
  "processing_status": "PASS",
  "overall_confidence": 0.98,
  "file_validation": {
    "file_type": "application/pdf",
    "is_supported": true,
    "is_readable": true,
    "page_count": 1,
    "status": "PASS"
  },
  "extracted_data": {
    "invoice_number": {
      "value": "INV-23891",
      "confidence": 0.99,
      "page_number": 1,
      "evidence": { "source_text": "Invoice No: INV-23891", "page_number": 1 }
    },
    "subtotal": { "value": 12500.0, "confidence": 0.98, "page_number": 1 },
    "tax_amount": { "value": 625.0, "confidence": 0.97, "page_number": 1 },
    "discount": { "value": 0.0, "confidence": 0.95, "page_number": 1 },
    "total_amount": { "value": 13125.0, "confidence": 0.99, "page_number": 1 },
    "line_items": [
      { "description": "Cloud Consulting", "quantity": 1.0, "unit_price": 12500.0, "amount": 12500.0 }
    ]
  },
  "validation": {
    "checks": [
      {
        "name": "invoice_total_check",
        "formula": "subtotal + tax_amount - discount",
        "operands": { "subtotal": 12500.0, "tax_amount": 625.0, "discount": 0.0 },
        "calculated_value": 13125.0,
        "reported_value": 13125.0,
        "variance": 0.0,
        "status": "PASS"
      }
    ],
    "overall_status": "PASS",
    "issues": []
  },
  "processing_metadata": {
    "ocr_used": false,
    "processed_at": "2026-09-08T12:00:00Z",
    "processing_time_ms": 1420
  }
}
```

### 2. Retrieve Latest Result by Document Name (GET)
```bash
curl -X GET "http://localhost:8000/api/v1/documents/sample_invoice.pdf"
```

### 3. List Processed Documents (GET)
```bash
curl -X GET "http://localhost:8000/api/v1/documents?limit=10"
```

### 4. Health Check (GET)
```bash
curl -X GET "http://localhost:8000/api/v1/health"
```

---

## 7. OCR & LLM Services Selected

- **OCR Strategy:** The system utilizes a hybrid model. Native PDF text is directly parsed with token boundary extraction (`PyPDF` / `PyMuPDF`). For scanned PDFs and image files (`PNG`, `JPG`), the platform leverages multimodal vision via Google Gemini (free-tier `gemini-2.5-flash` / `gemini-1.5-flash`) or local `pytesseract` if installed.
- **LLM Selection:** `gemini-2.5-flash` was selected due to its generous free tier, fast processing latency (< 2s for multi-page financial documents), native multimodal vision capabilities, and strict compliance with JSON Schema structured outputs.
- **Deterministic Heuristics:** When running in environments without internet access or API credentials, an intelligent rule-based extraction engine runs automatically, extracting clean key-value fields, line items, and evidence grounding.

---

## 8. Evidence Grounding & Confidence Scoring

- **Evidence Grounding:** Each key field returns an `evidence` object containing the exact snippet from the document (`source_text`) and the 1-indexed `page_number`.
- **Explainable Confidence:** Confidence scores (0.0 to 1.0) are calculated from:
  - Exact token match and format conformance (e.g. standard invoice number syntax &rarr; 0.98+).
  - OCR signal clarity and presence of anchor keywords (e.g., "Invoice Number:", "Total Amount:").
  - Missing or unreadable fields return `null` with confidence `0.0`.
  - Values with confidence below 80% are highlighted in yellow on the frontend.

---

## 9. Financial Validation Rules & Tolerance

The financial validation engine runs strict arithmetic checks as defined in Section 4.4:

1. **Invoice:**
   - Line Item: `Quantity * Unit Price ≈ Line Total`
   - Line Items Sum: `Sum(Line Totals) ≈ Subtotal or Total`
   - Invoice Total: `Subtotal + Tax Amount - Discount ≈ Total Amount` (supports GST-inclusive scenarios)
   - Cash Change: `Cash Paid - Total Amount ≈ Change`
2. **Balance Sheet:**
   - Equation: `Total Capital & Liabilities ≈ Total Assets` (or `Liabilities + Equity ≈ Assets`)
   - Components Sum: `Sum(Asset Components) ≈ Total Assets`
   - Independent verification across multi-year comparative periods.
3. **Profit & Loss:**
   - Total Income: `Interest Earned (or Revenue) + Other Income ≈ Total Income`
   - Total Expenditure: `Interest Expended + Operating Expenses + Provisions ≈ Total Expenditure`
   - Profit Reconciliation: `Total Income - Total Expenditure ≈ Profit Before Minority Interest`
   - Attributable Profit: `Profit Before Minority - Minority Interest ≈ Consolidated Net Profit`
   - Appropriation: `Current Profit + Brought Forward Profit ≈ Total Available for Appropriation`
4. **Cash Flow Statement:**
   - Net Change: `Operating + Investing + Financing + FX Adjustment ≈ Net Increase in Cash`
   - Closing Cash: `Opening Cash + Net Increase + Adjustments ≈ Closing Cash`
   - Bracket Parsing: Parentheses (e.g. `(45,000)`) are treated as negative floats (`-45000.0`).

**Non-Assumption Rule:** If a required field is not present in the document, the check status returns `NOT_APPLICABLE` instead of assuming zero.  
**Tolerance:** Absolute variance threshold $\le 0.05$ (configurable in `.env`).

---

## 10. Database & Persistence Approach

- **Storage Engine:** SQLite (local/embedded) and PostgreSQL (production).
- **ORM:** SQLAlchemy with declarative data model `ProcessedDocument`.
- **Data Retention:** Stores file validation details, extracted data, validation checks, issues, processing time, and timestamps.
- **Querying:** `DocumentRepository` abstracts database queries, supporting pagination, filtering by document type, and retrieval of the latest processed version for any document filename.

---

## 11. Known Limitations & Production Improvements

### Known Limitations
1. **Multi-Column OCR:** Highly complex multi-column tables with merged cells in low-resolution scans may experience line misalignment without layout-aware vision models.
2. **Synchronous Execution:** Long-running documents (> 15 seconds) block the immediate HTTP request cycle.

### What Would Change in Production
1. **Asynchronous Task Queue:** Transition file upload to an async workflow using **Celery** with **Redis** / **RabbitMQ**, returning an ingestion task ID with websocket progress notifications.
2. **Cloud Object Storage:** Persist documents in AWS S3 or Google Cloud Storage with presigned URLs instead of the local filesystem.
3. **High-Availability Database:** Use Amazon RDS PostgreSQL with connection pooling (PgBouncer).
4. **Authentication & RBAC:** Implement JWT / OAuth2 authentication with multi-tenant workspace isolation.
5. **Observability:** Instrument OpenTelemetry metrics, Prometheus counters, and Sentry error monitoring.

---

## 12. AI Coding Assistants Used

In compliance with Section 14 (Permitted Use of Generative AI):
- **Antigravity / Gemini:** Used for architecture scaffolding, regex verification, test case generation, and design of frontend templates.
- **All generated code and validation algorithms were verified, unit-tested, and audited.**
=======
# intelligent-document-extraction
>>>>>>> 7a333c87096f08b06f6c942865888c5ca8bcfe5f
