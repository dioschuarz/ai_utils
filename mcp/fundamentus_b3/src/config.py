"""Configuration helpers for the Fundamentus MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    mcp_host: str
    mcp_port: int
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    db_sslmode: str
    db_schema: str
    cache_ttl_hours: int


def get_settings() -> Settings:
    return Settings(
        mcp_host=os.getenv("MCP_HOST", "0.0.0.0"),
        mcp_port=int(os.getenv("MCP_PORT", "8000")),
        db_host=os.getenv("POSTGRES_HOST", "host.docker.internal"),
        db_port=int(os.getenv("POSTGRES_PORT", "5432")),
        db_name=os.getenv("POSTGRES_DB", "postgres"),
        db_user=os.getenv("POSTGRES_USER", "postgres.your-tenant-id"),
        db_password=os.getenv("POSTGRES_PASSWORD", "your-super-secret-and-long-postgres-password"),
        db_sslmode=os.getenv("POSTGRES_SSLMODE", "disable"),
        db_schema=os.getenv("POSTGRES_SCHEMA", "fundamentus"),
        cache_ttl_hours=int(os.getenv("CACHE_TTL_HOURS", "24")),
    )
