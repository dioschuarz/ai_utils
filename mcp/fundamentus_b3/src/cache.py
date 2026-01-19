"""Cache management for B3 stock data."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

import numpy as np
import pandas as pd

from config import get_settings
from db import get_conn

logger = logging.getLogger(__name__)


def _make_json_serializable(obj: Any) -> Any:
    """
    Recursively convert numpy/pandas types to Python native types for JSON serialization.
    
    Args:
        obj: Any object that might contain numpy/pandas types
        
    Returns:
        Object with all numpy/pandas types converted to Python native types
    """
    if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    if pd.isna(obj):
        return None
    return obj


def get_cached(ticker: str) -> Dict[str, Any] | None:
    """
    Get cached data for a ticker if it exists and is not expired.
    
    Args:
        ticker: Stock ticker (will be normalized)
        
    Returns:
        Cached data dictionary or None if not found/expired
    """
    from fundamentus_client import normalize_ticker
    
    normalized_ticker = normalize_ticker(ticker)
    
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT data, expires_at
                    FROM b3_stock_cache
                    WHERE ticker = %s
                      AND expires_at > CURRENT_TIMESTAMP
                    """,
                    (normalized_ticker,),
                )
                row = cur.fetchone()
                
                if row:
                    logger.debug(f"Cache hit for {normalized_ticker}")
                    return dict(row["data"])
                else:
                    logger.debug(f"Cache miss for {normalized_ticker}")
                    return None
                    
    except Exception as e:
        logger.error(f"Error reading cache for {normalized_ticker}: {e}")
        return None


def save_to_cache(ticker: str, data: Dict[str, Any]) -> None:
    """
    Save or update cached data for a ticker.
    
    Args:
        ticker: Stock ticker (will be normalized)
        data: Data dictionary to cache
    """
    from fundamentus_client import normalize_ticker
    
    normalized_ticker = normalize_ticker(ticker)
    settings = get_settings()
    
    now = datetime.utcnow()
    expires_at = now + timedelta(hours=settings.cache_ttl_hours)
    
    try:
        # Ensure data is JSON serializable before saving
        serializable_data = _make_json_serializable(data)
        
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO b3_stock_cache (ticker, data, created_at, updated_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (ticker) DO UPDATE
                    SET data = EXCLUDED.data,
                        updated_at = EXCLUDED.updated_at,
                        expires_at = EXCLUDED.expires_at
                    """,
                    (
                        normalized_ticker,
                        json.dumps(serializable_data),
                        now,
                        now,
                        expires_at,
                    ),
                )
            conn.commit()
            logger.debug(f"Cached data for {normalized_ticker} (expires at {expires_at})")
            
    except Exception as e:
        logger.error(f"Error saving cache for {normalized_ticker}: {e}")
        raise


def is_expired(ticker: str) -> bool:
    """
    Check if cached data for a ticker is expired.
    
    Args:
        ticker: Stock ticker (will be normalized)
        
    Returns:
        True if expired or not found, False if valid
    """
    from fundamentus_client import normalize_ticker
    
    normalized_ticker = normalize_ticker(ticker)
    
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT expires_at
                    FROM b3_stock_cache
                    WHERE ticker = %s
                    """,
                    (normalized_ticker,),
                )
                row = cur.fetchone()
                
                if not row:
                    return True  # Not found = expired
                
                expires_at = row["expires_at"]
                return expires_at <= datetime.utcnow()
                
    except Exception as e:
        logger.error(f"Error checking expiration for {normalized_ticker}: {e}")
        return True  # On error, consider expired


def clear_expired() -> int:
    """
    Remove expired cache entries.
    
    Returns:
        Number of entries removed
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM b3_stock_cache
                    WHERE expires_at <= CURRENT_TIMESTAMP
                    """
                )
                count = cur.rowcount
            conn.commit()
            logger.info(f"Cleared {count} expired cache entries")
            return count
            
    except Exception as e:
        logger.error(f"Error clearing expired cache: {e}")
        return 0


def list_cached_tickers() -> list[str]:
    """
    List all tickers that have valid (non-expired) cache entries.
    
    Returns:
        List of ticker symbols
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ticker
                    FROM b3_stock_cache
                    WHERE expires_at > CURRENT_TIMESTAMP
                    ORDER BY ticker
                    """
                )
                rows = cur.fetchall()
                return [row["ticker"] for row in rows]
                
    except Exception as e:
        logger.error(f"Error listing cached tickers: {e}")
        return []
