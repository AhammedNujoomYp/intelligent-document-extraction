# Production Dockerfile for Intelligent Document Extraction Platform
FROM python:3.11-slim

# Install system dependencies (including tesseract for OCR support)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency specifications
COPY backend/requirements.txt /app/backend/requirements.txt

# Install python dependencies
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy source code
COPY backend /app/backend
COPY frontend /app/frontend
COPY sample_outputs /app/sample_outputs
COPY .env.example /app/.env.example

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

# Create uploads directory
RUN mkdir -p /app/uploads

EXPOSE 8000

# Start FastAPI application with Uvicorn
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
