"""Main FastAPI Application Entry Point."""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, status, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from backend.app.api.routes.documents import router as documents_router
from backend.app.core.config import settings
from backend.app.core.database import get_db, init_db
from backend.app.core.logging import logger
from backend.app.services.document_service import DocumentService
from backend.app.utils.helpers import DocumentProcessingException


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    logger.info("Initializing Intelligent Document Extraction Platform...")
    init_db()
    logger.info("Application startup completed successfully.")
    yield


app = FastAPI(
    title="Intelligent Document Extraction, Validation & API Platform",
    description="End-to-end AI document intelligence service extracting fields, validating financial integrity, and persisting structured data.",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Ensure database tables exist immediately
init_db()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files & Template paths
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
static_dir = frontend_dir / "static"
templates_dir = frontend_dir / "templates"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

templates = Jinja2Templates(directory=str(templates_dir))

# Include API Router
app.include_router(documents_router, prefix=settings.API_V1_PREFIX)


# ------------------------------------------------------------------------------
# FRONTEND UI ROUTES
# ------------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard_view(request: Request, db: Session = Depends(get_db)):
    """Render the dashboard UI page."""
    service = DocumentService(db)
    docs = service.list_documents(limit=100)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "documents": docs, "api_base": settings.API_V1_PREFIX}
    )


@app.get("/documents/{doc_id}", response_class=HTMLResponse, include_in_schema=False)
def document_result_view(doc_id: int, request: Request, db: Session = Depends(get_db)):
    """Render the detailed document extraction and validation result page."""
    service = DocumentService(db)
    doc_dict = service.get_by_id(doc_id)
    if not doc_dict:
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "error": f"Document ID {doc_id} not found.",
                "documents": service.list_documents(limit=100),
                "api_base": settings.API_V1_PREFIX
            },
            status_code=404
        )
    return templates.TemplateResponse(
        "document_result.html",
        {"request": request, "doc": doc_dict, "api_base": settings.API_V1_PREFIX}
    )


# ------------------------------------------------------------------------------
# GLOBAL EXCEPTION HANDLERS (Section 5.3 Compliance)
# ------------------------------------------------------------------------------
@app.exception_handler(DocumentProcessingException)
async def custom_doc_exception_handler(request: Request, exc: DocumentProcessingException):
    """Handles controlled document processing errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handles FastAPI parameter/body validation errors in Section 5.3 format."""
    logger.warning(f"Request validation error on {request.url}: {exc}")
    errors = exc.errors()
    msg = errors[0].get("msg", "Invalid request parameters.") if errors else "Invalid request."
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": {"code": "VALIDATION_ERROR", "message": msg}}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Prevents stack traces and secrets from leaking to users."""
    logger.error(f"Unhandled server error on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred. Please check service logs."
            }
        }
    )
