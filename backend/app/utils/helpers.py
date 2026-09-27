"""Utility functions for numerical parsing, validation, and file inspection."""

import re
from typing import Optional, Tuple


class DocumentProcessingException(Exception):
    """Custom exception containing structured error details."""
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def parse_numeric(val: any) -> Optional[float]:
    """
    Parses a financial number from various string or numeric formats.
    Handles:
      - Parentheses for negative numbers: '(1,250.00)' -> -1250.00
      - Currency symbols: '$ 1,250.50', 'USD 1250', '€ 500', '₹ 1000'
      - Thousand separators: '1,234,567.89' or European '1.234.567,89'
      - Trailing or leading minus signs: '150-' -> -150.0
      - None / empty string returns None
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s or s.lower() in ("null", "none", "n/a", "-", "--", ""):
        return None

    is_negative = False

    # Check for parentheses indicating negative: (1,234.56)
    if (s.startswith("(") and s.endswith(")")) or (s.startswith("[") and s.endswith("]")):
        is_negative = True
        s = s[1:-1].strip()
    elif s.startswith("-"):
        is_negative = True
        s = s[1:].strip()
    elif s.endswith("-"):
        is_negative = True
        s = s[:-1].strip()

    # Strip currency symbols and letters
    s = re.sub(r"[^\d.,]", "", s)
    if not s:
        return None

    # Handle comma/dot decimal conventions:
    # If both '.' and ',' appear:
    if "." in s and "," in s:
        last_dot = s.rfind(".")
        last_comma = s.rfind(",")
        if last_dot > last_comma:
            # Standard: 1,234.56 -> remove commas
            s = s.replace(",", "")
        else:
            # European: 1.234,56 -> remove dots, replace comma with dot
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        # Only commas: could be '1,234' (thousands) or '12,50' (decimal)
        parts = s.split(",")
        if len(parts[-1]) == 2:  # Likely decimal cents: 12,50
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")

    try:
        num = float(s)
        return -num if is_negative else num
    except (ValueError, TypeError):
        return None


def detect_file_type(filename: str, file_bytes: bytes) -> Tuple[str, bool]:
    """
    Detects MIME type using magic header bytes and file extension.
    Returns (mime_type, is_supported).
    """
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    
    # Check magic bytes
    if file_bytes.startswith(b"%PDF"):
        return "application/pdf", True
    elif file_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", True
    elif file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", True

    # Fallback to extension check if magic bytes are obscured
    if ext == "pdf":
        return "application/pdf", True
    elif ext in ("jpg", "jpeg"):
        return "image/jpeg", True
    elif ext == "png":
        return "image/png", True

    return f"application/octet-stream ({ext})", False


def compare_with_tolerance(val1: Optional[float], val2: Optional[float], tolerance: float = 0.05) -> Tuple[bool, Optional[float]]:
    """
    Compares two floats with an absolute tolerance.
    Returns (matches, variance).
    """
    if val1 is None or val2 is None:
        return False, None
    variance = round(abs(val1 - val2), 2)
    return variance <= tolerance, variance
