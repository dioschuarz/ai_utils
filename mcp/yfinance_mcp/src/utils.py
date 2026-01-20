import json
from typing import Optional

from .yfinance_types import ErrorCode


def dump_json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def create_error_response(message: str, error_code: ErrorCode = "UNKNOWN_ERROR", details: dict | None = None) -> str:
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


def extract_urls_from_news(news_data: list[dict]) -> tuple[list[str], list[Optional[str]]]:
    """Extract URLs and titles from news data.

    Args:
        news_data: List of news items from yfinance_get_ticker_news

    Returns:
        Tuple of (urls, titles) lists
    """
    urls = []
    titles = []

    for item in news_data:
        url = None
        title = None

        if "content" in item and isinstance(item["content"], dict):
            content = item["content"]

            # Extract title
            title = content.get("title", "")

            # Extract URL from canonicalUrl (inside content)
            if "canonicalUrl" in content and isinstance(content["canonicalUrl"], dict):
                url = content["canonicalUrl"].get("url")
            # Fallback: try clickThroughUrl
            elif "clickThroughUrl" in content:
                url = content.get("clickThroughUrl")

        # Validate and add URL
        if url and url.startswith(("http://", "https://")):
            urls.append(url)
            titles.append(title if title else None)

    return urls, titles
