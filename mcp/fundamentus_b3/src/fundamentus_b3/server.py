"""FastMCP server exposing Fundamentus B3 stock data tools."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from mcp.server.fastmcp import FastMCP

from fundamentus_b3.cache import (
    clear_expired,
    get_cached,
    list_cached_tickers as list_cached_tickers_from_cache,
    save_to_cache,
)
from fundamentus_b3.config import get_settings
from fundamentus_b3.fundamentus_client import (
    get_papel_data,
    normalize_ticker,
    search_tickers as search_tickers_client,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_settings = get_settings()
mcp = FastMCP(
    "fundamentus-b3",
    host=_settings.mcp_host,
    port=_settings.mcp_port,
)


@mcp.tool()
def get_b3_snapshot(ticker: str) -> Dict[str, Any]:
    """
    Get a complete snapshot of a B3 stock ticker.
    
    Uses cache if available and valid, otherwise fetches from Fundamentus
    and caches the result.
    
    Args:
        ticker: Stock ticker (e.g., "PETR4", "PETR4.SA")
        
    Returns:
        Dictionary with complete stock snapshot data
    """
    normalized_ticker = normalize_ticker(ticker)
    
    # Try cache first
    cached = get_cached(normalized_ticker)
    if cached:
        logger.info(f"Returning cached data for {normalized_ticker}")
        return {"ticker": normalized_ticker, "data": cached, "source": "cache"}
    
    # Cache miss or expired - fetch from Fundamentus
    try:
        logger.info(f"Fetching data from Fundamentus for {normalized_ticker}")
        data = get_papel_data(normalized_ticker)
        
        # Save to cache
        save_to_cache(normalized_ticker, data)
        
        return {"ticker": normalized_ticker, "data": data, "source": "fundamentus"}
        
    except ValueError as e:
        return {"error": str(e), "ticker": normalized_ticker}
    except Exception as e:
        logger.error(f"Unexpected error fetching {normalized_ticker}: {e}")
        return {"error": f"Failed to fetch data: {str(e)}", "ticker": normalized_ticker}


@mcp.tool()
def get_b3_snapshots(tickers: List[str]) -> Dict[str, Any]:
    """
    Get snapshots for multiple B3 stock tickers in batch.
    
    Optimizes queries by checking cache first, then fetching from Fundamentus
    only for cache misses.
    
    Args:
        tickers: List of stock tickers (e.g., ["PETR4", "VALE3", "ITUB4"])
        
    Returns:
        Dictionary with results for each ticker
    """
    results = {}
    normalized_tickers = [normalize_ticker(t) for t in tickers]
    
    # First pass: check cache for all tickers
    cache_hits = {}
    cache_misses = []
    
    for ticker in normalized_tickers:
        cached = get_cached(ticker)
        if cached:
            cache_hits[ticker] = cached
            results[ticker] = {"data": cached, "source": "cache"}
        else:
            cache_misses.append(ticker)
            results[ticker] = None  # Placeholder
    
    logger.info(f"Cache hits: {len(cache_hits)}, Cache misses: {len(cache_misses)}")
    
    # Second pass: fetch from Fundamentus for cache misses
    for ticker in cache_misses:
        try:
            logger.info(f"Fetching data from Fundamentus for {ticker}")
            data = get_papel_data(ticker)
            save_to_cache(ticker, data)
            results[ticker] = {"data": data, "source": "fundamentus"}
        except ValueError as e:
            results[ticker] = {"error": str(e)}
        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}")
            results[ticker] = {"error": f"Failed to fetch data: {str(e)}"}
    
    return {
        "results": results,
        "summary": {
            "total": len(normalized_tickers),
            "cache_hits": len(cache_hits),
            "cache_misses": len(cache_misses),
        },
    }


@mcp.tool()
def get_fundamental_metrics(ticker: str) -> Dict[str, Any]:
    """
    Get essential fundamental metrics for a B3 stock ticker.
    
    Extracts comprehensive metrics organized by category:
    - Valuation: P/L, P/VP, DY, EV/EBITDA, etc.
    - Profitability: ROIC, ROE, Margins
    - Solvency: D/E Ratio, Interest Coverage Ratio (ICR), Debt ratios
    - Liquidity: Current Ratio, Cash, Working Capital
    - Balance Sheet: Assets, Liabilities, Equity
    - Income Statement: Revenue, EBIT, EBITDA, Net Income
    
    Args:
        ticker: Stock ticker (e.g., "PETR4")
        
    Returns:
        Dictionary with essential fundamental metrics organized by category
    """
    normalized_ticker = normalize_ticker(ticker)
    
    # Get full snapshot (uses cache if available)
    snapshot = get_b3_snapshot(normalized_ticker)
    
    if "error" in snapshot:
        return snapshot
    
    data = snapshot.get("data", {})
    
    # Extract metrics using the new categorized structure
    # If categories exist, use them; otherwise fall back to flat structure
    if "valuation" in data:
        # New structure with categories
        metrics = {
            "ticker": normalized_ticker,
            "valuation": data.get("valuation", {}),
            "profitability": data.get("profitability", {}),
            "solvency": data.get("solvency", {}),
            "liquidity": data.get("liquidity", {}),
            "balance_sheet": data.get("balance_sheet", {}),
            "income_statement": data.get("income_statement", {}),
            "efficiency": data.get("efficiency", {}),
            "growth": data.get("growth", {}),
        }
    else:
        # Fallback to flat structure (backward compatibility)
        metrics = {
            "ticker": normalized_ticker,
            "cotacao": data.get("cotacao"),
            "p_l": data.get("pl"),
            "pvp": data.get("pvp"),
            "dy": data.get("dy"),
            "debt_to_equity": data.get("div_bruta_patrim") or data.get("div_brut_patrim"),
            "interest_coverage": data.get("ebit_juros"),
            "roic": data.get("roic"),
            "roe": data.get("roe"),
            "operating_margin": data.get("marg_ebit"),
            "net_margin": data.get("marg_liquida"),
            "ev_ebitda": data.get("ev_ebitda"),
            "divida_liquida": data.get("divida_liquida"),
            "caixa": data.get("caixa"),
            "patrimonio_liquido": data.get("patrimonio_liquido"),
            "ebit_12m": data.get("ebit_12m"),
            "receita_liquida_12m": data.get("receita_liquida_12m"),
        }
    
    # Remove None values from nested structures
    def clean_dict(d):
        if isinstance(d, dict):
            return {k: clean_dict(v) for k, v in d.items() if v is not None}
        return d
    
    metrics = clean_dict(metrics)
    
    return metrics


@mcp.tool()
def search_tickers(query: str) -> Dict[str, Any]:
    """
    Search for B3 stock tickers by name or segment.
    
    Args:
        query: Search query (ticker code or company name)
        
    Returns:
        Dictionary with list of matching tickers
    """
    try:
        results = search_tickers_client(query)
        return {
            "query": query,
            "count": len(results),
            "tickers": results,
        }
    except Exception as e:
        logger.error(f"Error searching tickers: {e}")
        return {"error": f"Failed to search tickers: {str(e)}", "query": query}


@mcp.tool()
def refresh_cache(ticker: str) -> Dict[str, Any]:
    """
    Force refresh of cached data for a ticker, ignoring TTL.
    
    Useful for critical data that needs to be up-to-date.
    
    Args:
        ticker: Stock ticker (e.g., "PETR4")
        
    Returns:
        Dictionary with refreshed data
    """
    normalized_ticker = normalize_ticker(ticker)
    
    try:
        logger.info(f"Force refreshing cache for {normalized_ticker}")
        data = get_papel_data(normalized_ticker)
        save_to_cache(normalized_ticker, data)
        
        return {
            "ticker": normalized_ticker,
            "data": data,
            "source": "fundamentus",
            "refreshed": True,
        }
    except ValueError as e:
        return {"error": str(e), "ticker": normalized_ticker}
    except Exception as e:
        logger.error(f"Error refreshing {normalized_ticker}: {e}")
        return {"error": f"Failed to refresh: {str(e)}", "ticker": normalized_ticker}


@mcp.tool()
def list_cached_tickers() -> Dict[str, Any]:
    """
    List all tickers that have valid (non-expired) cache entries.
    
    Useful for debugging and monitoring.
    
    Returns:
        Dictionary with list of cached tickers
    """
    try:
        tickers = list_cached_tickers_from_cache()
        return {
            "count": len(tickers),
            "tickers": tickers,
        }
    except Exception as e:
        logger.error(f"Error listing cached tickers: {e}")
        return {"error": f"Failed to list cached tickers: {str(e)}"}


def main() -> None:
    """Run the MCP server."""
    # Clear expired entries on startup
    cleared = clear_expired()
    if cleared > 0:
        logger.info(f"Cleared {cleared} expired cache entries on startup")
    
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()

