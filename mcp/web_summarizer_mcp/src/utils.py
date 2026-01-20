"""Utility functions for error handling and response formatting."""

import json
from typing import Literal

ErrorCode = Literal[
    "INVALID_URL",
    "CRAWL_TIMEOUT",
    "CRAWL_ERROR",
    "RATE_LIMIT_EXCEEDED",
    "GEMINI_ERROR",
    "TOKEN_LIMIT_EXCEEDED",
    "NETWORK_ERROR",
    "UNKNOWN_ERROR",
]


def dump_json(payload: object) -> str:
    """Serialize object to JSON string."""
    return json.dumps(payload, ensure_ascii=False, default=str, indent=2)


def create_error_response(
    message: str,
    error_code: ErrorCode = "UNKNOWN_ERROR",
    details: dict | None = None,
) -> str:
    """Create a structured error response.

    Args:
        message: Human-readable error message
        error_code: Machine-readable error code for client handling
        details: Optional additional error details

    Returns:
        JSON string with error information
    """
    error_obj = {"error": message, "error_code": error_code}
    if details:
        error_obj["details"] = details
    return dump_json(error_obj)


def estimate_tokens(text: str) -> int:
    """Estimate token count for a given text.

    Uses a simple heuristic: ~4 characters per token for English/Portuguese text.
    This is a rough estimate; actual tokenization varies by model.

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count
    """
    # Rough estimate: 4 characters per token
    # This is conservative and works reasonably well for most text
    return len(text) // 4
