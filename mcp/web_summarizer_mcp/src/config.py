"""Configuration helpers for the Web Summarizer MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    mcp_host: str
    mcp_port: int
    gemini_api_key: str
    gemini_model: str
    max_urls_per_request: int
    max_tokens_per_minute: int
    max_requests_per_minute: int
    crawl_timeout_seconds: int
    crawl_max_retries: int
    max_concurrent_requests: int


def get_settings() -> Settings:
    """Load and return settings from environment variables."""
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY environment variable is required. "
            "Please set it in your .env file or environment."
        )

    return Settings(
        mcp_host=os.getenv("MCP_HOST", "0.0.0.0"),
        mcp_port=int(os.getenv("MCP_PORT", "8000")),
        gemini_api_key=gemini_api_key,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp"),
        max_urls_per_request=int(os.getenv("MAX_URLS_PER_REQUEST", "10")),
        max_tokens_per_minute=int(os.getenv("MAX_TOKENS_PER_MINUTE", "4000000")),
        max_requests_per_minute=int(os.getenv("MAX_REQUESTS_PER_MINUTE", "4000")),
        crawl_timeout_seconds=int(os.getenv("CRAWL_TIMEOUT_SECONDS", "30")),
        crawl_max_retries=int(os.getenv("CRAWL_MAX_RETRIES", "2")),
        max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", "5")),
    )
