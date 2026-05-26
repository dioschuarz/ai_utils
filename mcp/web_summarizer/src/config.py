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
    openrouter_api_key: str
    openrouter_intermediate_model: str
    cerebras_api_key: str | None
    cerebras_models: str
    cerebras_rpm: int
    provider_priority: str
    llm_timeout: int
    max_urls_per_request: int
    max_tokens_per_minute: int
    max_requests_per_minute: int
    crawl_timeout_seconds: int
    crawl_max_retries: int
    max_concurrent_requests: int


def get_settings() -> Settings:
    """Load and return settings from environment variables."""
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        raise ValueError(
            "OPENROUTER_API_KEY environment variable is required. "
            "Please set it in your .env file or environment."
        )

    return Settings(
        mcp_host=os.getenv("MCP_HOST", "0.0.0.0"),
        mcp_port=int(os.getenv("MCP_PORT", "8000")),
        openrouter_api_key=openrouter_api_key,
        openrouter_intermediate_model=os.getenv("OPENROUTER_INTERMEDIATE_MODEL", "google/gemini-2.0-flash-001"),
        cerebras_api_key=os.getenv("CEREBRAS_API_KEY"),
        cerebras_models=os.getenv("CEREBRAS_MODELS", "llama3.1-8b"),
        cerebras_rpm=int(os.getenv("CEREBRAS_RPM", "30")),
        provider_priority=os.getenv("PROVIDER_PRIORITY", "cerebras;openrouter"),
        llm_timeout=int(os.getenv("LLM_TIMEOUT", "120")),
        max_urls_per_request=int(os.getenv("MAX_URLS_PER_REQUEST", "10")),
        max_tokens_per_minute=int(os.getenv("MAX_TOKENS_PER_MINUTE", "4000000")),
        max_requests_per_minute=int(os.getenv("MAX_REQUESTS_PER_MINUTE", "15")),
        crawl_timeout_seconds=int(os.getenv("CRAWL_TIMEOUT_SECONDS", "30")),
        crawl_max_retries=int(os.getenv("CRAWL_MAX_RETRIES", "2")),
        max_concurrent_requests=int(os.getenv("MAX_CONCURRENT_REQUESTS", "10")),
    )
