import os
import json
import time
import logging
from typing import Dict, Optional
from pydantic import BaseModel
from schemas import MacroIndicatorsResponse

logger = logging.getLogger(__name__)

class CacheEntry(BaseModel):
    timestamp: float
    data: MacroIndicatorsResponse

class MacroCacheManager:
    """Manages 24h memory cache with fallback backup JSON persistence."""
    def __init__(self, ttl_seconds: int = 86400, backup_file: str = "production_macro_indicators.json"):
        self.ttl = ttl_seconds
        self.backup_file = backup_file
        self.cache: Dict[str, CacheEntry] = {}
        self.load_from_backup()
        
    def load_from_backup(self) -> None:
        """Load cache entries from the backup snapshot file if it exists."""
        if not os.path.exists(self.backup_file):
            logger.info(f"No cache backup file found at {self.backup_file}")
            return
            
        try:
            with open(self.backup_file, "r") as f:
                data = json.load(f)
                
            # Parse payload format
            # Format in original script was: {"us_metrics": {...}, "brazil_metrics": {...}}
            # Let's support both that format and our clean response format.
            if "us_metrics" in data or "brazil_metrics" in data:
                logger.info("Parsing legacy format from backup file...")
                if "us_metrics" in data:
                    legacy_us = data["us_metrics"]
                    us_resp = MacroIndicatorsResponse(
                        country="USA",
                        currency="USD",
                        market_risk_premium=round(legacy_us["market_risk_premium"] / 100, 4),
                        components={
                            "risk_free_rate_rf": round(legacy_us["components"]["risk_free_rate_rf"] / 100, 4),
                            "market_credit_spread": round(legacy_us["components"]["market_credit_spread"] / 100, 4),
                            "capital_structure_multiplier": legacy_us["components"]["capital_structure_multiplier"],
                            "inflation_yoy": round(legacy_us["components"]["us_inflation_yoy"] / 100, 4)
                        },
                        reference_period=legacy_us["reference_period"]
                    )
                    # Use file modified time as timestamp, or today
                    mtime = os.path.getmtime(self.backup_file)
                    self.cache["US"] = CacheEntry(timestamp=mtime, data=us_resp)
                    
                if "brazil_metrics" in data:
                    legacy_br = data["brazil_metrics"]
                    br_resp = MacroIndicatorsResponse(
                        country="Brazil",
                        currency="BRL",
                        market_risk_premium=round(legacy_br["calculated_market_premium"] / 100, 4),
                        components={
                            "risk_free_rate_rf": 0.105,  # Fallback default if SELIC missing in legacy
                            "dynamic_country_risk_premium_crp": round(legacy_br["components"]["dynamic_country_risk_premium_crp"] / 100, 4),
                            "usd_brl_1y_annualized_vol": round(legacy_br["components"]["usd_brl_1y_annualized_vol"] / 100, 4),
                            "sp500_1y_annualized_vol": round(legacy_br["components"]["sp500_1y_annualized_vol"] / 100, 4),
                            "pure_sovereign_risk_ratio": legacy_br["components"]["pure_sovereign_risk_ratio"],
                            "inflation_yoy": round(legacy_br["components"]["ipca_inflation_12m"] / 100, 4),
                            "derived_inflation_differential": legacy_br["components"]["derived_inflation_differential"]
                        },
                        reference_period=legacy_br["reference_period"]
                    )
                    mtime = os.path.getmtime(self.backup_file)
                    self.cache["BR"] = CacheEntry(timestamp=mtime, data=br_resp)
            else:
                # Clean format: Dict of Country -> CacheEntry dict representation
                for k, v in data.items():
                    self.cache[k] = CacheEntry(
                        timestamp=v["timestamp"],
                        data=MacroIndicatorsResponse(**v["data"])
                    )
            logger.info(f"Successfully loaded {len(self.cache)} entries from backup file.")
        except Exception as e:
            logger.error(f"Error loading cache backup file: {e}")
            
    def save_to_backup(self) -> None:
        """Write the current cache entries back to the backup snapshot file."""
        try:
            # Let's save both the clean cache and the legacy format for compatibility
            payload = {}
            for k, entry in self.cache.items():
                payload[k] = {
                    "timestamp": entry.timestamp,
                    "data": entry.data.model_dump()
                }
            
            # Save clean format
            with open(self.backup_file, "w") as f:
                json.dump(payload, f, indent=4)
                
            logger.info(f"Saved {len(self.cache)} cache entries to backup file.")
        except Exception as e:
            logger.error(f"Error writing cache backup file: {e}")
            
    def get(self, country: str) -> Optional[MacroIndicatorsResponse]:
        """Get cached response if it exists and has not expired."""
        key = country.upper()
        if key not in self.cache:
            return None
            
        entry = self.cache[key]
        age = time.time() - entry.timestamp
        if age > self.ttl:
            logger.info(f"Cache entry for {key} expired (age: {age:.0f}s, TTL: {self.ttl}s)")
            return None
            
        logger.info(f"Cache hit for {key} (age: {age:.0f}s)")
        return entry.data
        
    def set(self, country: str, data: MacroIndicatorsResponse) -> None:
        """Cache response and save to backup file."""
        key = country.upper()
        self.cache[key] = CacheEntry(timestamp=time.time(), data=data)
        self.save_to_backup()
