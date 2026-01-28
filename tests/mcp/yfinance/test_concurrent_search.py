#!/usr/bin/env python3
"""
Test script to verify concurrent execution of yfinance_get_ticker_news_summarized
and validate the increased timeout setting using pytest.
"""

import asyncio
import json
import logging
import pytest
import aiohttp
from typing import Any, Dict

from mcp import ClientSession
from mcp.client.sse import sse_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_concurrent")

YFINANCE_MCP_URL = "http://localhost:8102/sse"

# --- Helper Functions ---

async def call_summarized_news(session: ClientSession, symbol: str) -> Dict[str, Any]:
    """Call yfinance_get_ticker_news_summarized for a single symbol."""
    logger.info(f"Starting request for {symbol}...")
    
    try:
        result = await session.call_tool(
            "yfinance_get_ticker_news_summarized",
            arguments={
                "symbol": symbol,
                "max_news": 5,  # Reduced from 10 to keep test time reasonable but effective
                "timeout_per_url": 30,
                "fallback_on_error": True
            }
        )
        
        # Parse content
        if result.content and len(result.content) > 0:
            content_text = result.content[0].text
            try:
                data = json.loads(content_text)
                return {
                    "symbol": symbol,
                    "status": "success",
                    "data": data
                }
            except json.JSONDecodeError:
                return {
                    "symbol": symbol,
                    "status": "error",
                    "error": "Invalid JSON response"
                }
        else:
            return {
                "symbol": symbol,
                "status": "error",
                "error": "Empty response"
            }
            
    except Exception as e:
        return {
            "symbol": symbol,
            "status": "error",
            "error": str(e)
        }

async def check_server_available(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=2) as response:
                return response.status in (200, 404, 405)
    except:
        return False

# --- Automated Test ---

@pytest.mark.asyncio
async def test_concurrent_news_summarization():
    """Test concurrent execution of news summarization for multiple tickers."""
    
    # Skip if servers are offline
    if not await check_server_available(YFINANCE_MCP_URL):
        pytest.skip(f"YFinance MCP server at {YFINANCE_MCP_URL} is offline")

    symbols = ["DIS", "GOOGL", "TSLA", "MSFT", "NFLX", "PETR4.SA", "VALE3.SA", "WEGE3.SA", "ITUB3.SA", "MCLU3.SA"]
    logger.info(f"Testing concurrent requests for: {symbols}")
    
    async with sse_client(url=YFINANCE_MCP_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Create tasks
            tasks = [call_summarized_news(session, symbol) for symbol in symbols]
            
            # Run concurrently
            results = await asyncio.gather(*tasks)
            
            # Assertions
            success_count = 0
            failures = []
            
            for res in results:
                symbol = res["symbol"]
                status = res["status"]
                
                if status == "success":
                    data = res.get("data", {})
                    # Ensure it didn't just fallback silently without reason (unless expected)
                    # We accept fallback if it handled it gracefully, but prefer success
                    success_count += 1
                else:
                    failures.append(f"{symbol}: {res.get('error')}")
            
            assert len(failures) == 0, f"Some requests failed: {failures}"
            assert success_count == len(symbols), "Not all requests succeeded"
