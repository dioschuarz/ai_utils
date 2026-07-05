import os
import logging
import httpx
from typing import Dict, Optional, Union

logger = logging.getLogger(__name__)

class MacroClient:
    """REST client for the Macro Indicators service."""
    def __init__(self, base_url: Optional[str] = None):
        if base_url:
            self.base_url = base_url
        else:
            # Check environment variables
            env_url = os.getenv("MACRO_INDICATORS_URL")
            if env_url:
                self.base_url = env_url.rstrip('/')
            elif os.getenv("POSTGRES_HOST") == "supabase-db":
                # Running inside docker compose network
                self.base_url = "http://macro-indicators-mcp:8000"
            else:
                # Running locally
                self.base_url = "http://localhost:8108"
                
        logger.info(f"Initialized MacroClient with base URL: {self.base_url}")

    def get_indicators(self, country: str) -> Dict[str, Union[str, float, Dict[str, float]]]:
        """Fetch macro indicators for a country (US or BR)."""
        clean_country = country.upper()
        if clean_country in ("BR", "BRL", "BRAZIL"):
            country_code = "BR"
        else:
            country_code = "US"
            
        url = f"{self.base_url}/indicators/{country_code}"
        
        try:
            logger.info(f"Fetching macro indicators from {url}")
            with httpx.Client(timeout=5.0) as client:
                response = client.get(url)
                if response.status_code == 200:
                    return response.json()
                logger.error(f"MacroIndicators service returned status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Error connecting to MacroIndicators service at {url}: {e}")
            
        raise RuntimeError("Failed to retrieve macro indicators from microservice")
