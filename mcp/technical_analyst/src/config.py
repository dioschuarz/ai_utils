"""Configuration helpers for the Technical Analyst MCP server."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    mcp_host: str
    mcp_port: int

def get_settings() -> Settings:
    return Settings(
        mcp_host=os.getenv("MCP_HOST", "0.0.0.0"),
        mcp_port=int(os.getenv("MCP_PORT", "8000")),
    )
