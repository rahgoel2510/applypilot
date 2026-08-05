"""Input validation middleware to reject SQL injection and XSS attack patterns."""

import re
from fastapi import Request, HTTPException, Depends


# SQL injection patterns (case-insensitive)
SQL_INJECTION_PATTERNS = [
    r"(?i)\bUNION\s+SELECT\b",
    r"(?i)\bDROP\s+TABLE\b",
    r"(?i)\bDROP\s+DATABASE\b",
    r"(?i)\bDELETE\s+FROM\b",
    r"(?i)\bINSERT\s+INTO\b",
    r"(?i)\bUPDATE\s+\w+\s+SET\b",
    r"(?i)\bALTER\s+TABLE\b",
    r"(?i)\bEXEC(\s+|\s*\()",
    r"(?i)\bEXECUTE(\s+|\s*\()",
    r"(?i)\bxp_cmdshell\b",
    r"(?i);\s*--",
    r"(?i)\bOR\s+1\s*=\s*1\b",
    r"(?i)\bAND\s+1\s*=\s*1\b",
    r"(?i)\bSELECT\s+\*\s+FROM\b",
    r"(?i)\bINFORMATION_SCHEMA\b",
    r"(?i)\bWAITFOR\s+DELAY\b",
    r"(?i)\bBENCHMARK\s*\(",
    r"(?i)\bSLEEP\s*\(",
]

# XSS patterns (case-insensitive)
XSS_PATTERNS = [
    r"(?i)<\s*script",
    r"(?i)</\s*script\s*>",
    r"(?i)\bjavascript\s*:",
    r"(?i)\bonerror\s*=",
    r"(?i)\bonload\s*=",
    r"(?i)\bonclick\s*=",
    r"(?i)\bonmouseover\s*=",
    r"(?i)\bonfocus\s*=",
    r"(?i)\bonchange\s*=",
    r"(?i)\bonsubmit\s*=",
    r"(?i)<\s*iframe",
    r"(?i)<\s*object",
    r"(?i)<\s*embed",
    r"(?i)<\s*svg\s+onload",
    r"(?i)\beval\s*\(",
    r"(?i)\bdocument\.cookie\b",
    r"(?i)\bdocument\.write\b",
    r"(?i)\bwindow\.location\b",
    r"(?i)<\s*img\s+[^>]*on\w+\s*=",
]

# Compiled regex for performance
_SQL_COMPILED = [re.compile(p) for p in SQL_INJECTION_PATTERNS]
_XSS_COMPILED = [re.compile(p) for p in XSS_PATTERNS]

# Length limits
MAX_QUERY_PARAM_LENGTH = 500
MAX_PATH_PARAM_LENGTH = 100


def _check_sql_injection(value: str) -> bool:
    """Return True if value matches a SQL injection pattern."""
    for pattern in _SQL_COMPILED:
        if pattern.search(value):
            return True
    return False


def _check_xss(value: str) -> bool:
    """Return True if value matches an XSS pattern."""
    for pattern in _XSS_COMPILED:
        if pattern.search(value):
            return True
    return False


def sanitize_string(s: str) -> str:
    """Strip dangerous characters from a string.

    Removes: < > ' " ; \\ ` and NULL bytes.
    Preserves normal text, spaces, punctuation (except the above).

    Args:
        s: The input string to sanitize.

    Returns:
        Sanitized string with dangerous characters removed.
    """
    # Remove null bytes
    s = s.replace("\x00", "")
    # Remove dangerous characters
    s = re.sub(r"[<>'\";\\`]", "", s)
    # Collapse excessive whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


class InputValidator:
    """FastAPI dependency that validates request parameters against attack patterns."""

    async def __call__(self, request: Request) -> None:
        """Validate query params and path params.

        Raises:
            HTTPException: 400 if a dangerous pattern or length violation is detected.
        """
        # Validate query parameters
        for key, value in request.query_params.items():
            if len(value) > MAX_QUERY_PARAM_LENGTH:
                raise HTTPException(
                    status_code=400,
                    detail=f"Query parameter '{key}' exceeds maximum length of {MAX_QUERY_PARAM_LENGTH} characters.",
                )
            if _check_sql_injection(value):
                raise HTTPException(
                    status_code=400,
                    detail=f"Query parameter '{key}' contains a potentially dangerous SQL pattern.",
                )
            if _check_xss(value):
                raise HTTPException(
                    status_code=400,
                    detail=f"Query parameter '{key}' contains a potentially dangerous script pattern.",
                )

        # Validate path parameters
        path_params = request.path_params
        for key, value in path_params.items():
            str_value = str(value)
            if len(str_value) > MAX_PATH_PARAM_LENGTH:
                raise HTTPException(
                    status_code=400,
                    detail=f"Path parameter '{key}' exceeds maximum length of {MAX_PATH_PARAM_LENGTH} characters.",
                )
            if _check_sql_injection(str_value):
                raise HTTPException(
                    status_code=400,
                    detail=f"Path parameter '{key}' contains a potentially dangerous SQL pattern.",
                )
            if _check_xss(str_value):
                raise HTTPException(
                    status_code=400,
                    detail=f"Path parameter '{key}' contains a potentially dangerous script pattern.",
                )


# Export as a FastAPI dependency
validate_input = Depends(InputValidator())
