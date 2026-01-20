"""Configuration helpers for the YFinance MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    mcp_host: str
    mcp_port: int
    web_summarizer_url: str
    web_summarizer_timeout: int
    max_news_to_summarize: int


def get_settings() -> Settings:
    # Determine web_summarizer URL based on environment
    web_summarizer_url = os.getenv("WEB_SUMMARIZER_URL")
    
    if not web_summarizer_url:
        # Try to detect Docker environment by checking if we can resolve the service name
        # or by checking common Docker indicators
        # Default: assume Docker network if MCP_HOST is 0.0.0.0 (typical in containers)
        # For local development, user should set WEB_SUMMARIZER_URL explicitly
        mcp_host = os.getenv("MCP_HOST", "0.0.0.0")
        
        # Check if we're likely in Docker (MCP_HOST=0.0.0.0 is typical in Docker)
        # In Docker Compose, services can reach each other by service name
        if mcp_host == "0.0.0.0":
            # Likely in Docker - use service name and internal port
            web_summarizer_url = "http://web-summarizer-mcp:8000/sse"
        else:
            # Local development - use localhost with exposed port
            web_summarizer_url = "http://localhost:8103/sse"
    
    return Settings(
        mcp_host=os.getenv("MCP_HOST", "0.0.0.0"),
        mcp_port=int(os.getenv("MCP_PORT", "8000")),
        web_summarizer_url=web_summarizer_url,
        web_summarizer_timeout=int(os.getenv("WEB_SUMMARIZER_TIMEOUT", "60")),
        max_news_to_summarize=int(os.getenv("MAX_NEWS_TO_SUMMARIZE", "10")),
    )
