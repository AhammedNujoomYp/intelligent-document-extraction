"""Application configuration using Pydantic Settings."""

import os
from pathlib import Path
from typing import List, Set
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings class."""
    
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    
    # Project Info
    PROJECT_NAME: str = "Intelligent Document Extraction Platform"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "production"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = ["*"]
    
    # Database
    DATABASE_URL: str = "sqlite:///./documents.db"
    
    # File Storage & Limits
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_BYTES: int = 15 * 1024 * 1024  # 15 MB
    MAX_PAGE_LIMIT: int = 3
    ALLOWED_EXTENSIONS: Set[str] = {"pdf", "jpg", "jpeg", "png"}
    ALLOWED_MIME_TYPES: Set[str] = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/jpg"
    }
    
    # Financial Calculation Validation
    FINANCIAL_TOLERANCE: float = 0.05
    
    # LLM & OCR Services
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OCR_ENGINE: str = "hybrid"  # options: hybrid, mupdf, llm_vision
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
