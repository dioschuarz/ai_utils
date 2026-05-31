import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../docker/.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000
    
    tavily_api_key: str = ""
    tickertick_api_url: str = "https://api.tickertick.com"

_settings = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
