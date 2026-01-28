#!/usr/bin/env python3
"""
Test script for Technical Analyst MCP.
Tests specific technical analysis tools for PETR4.SA and GOOGL.
"""

import sys
from pathlib import Path

# Add parent directory of 'tests' to path to allow importing mcp logic if needed, 
# though we are using the official mcp python client here.
# Assuming we run from root or tests dir.

import pytest
import aiohttp
import json
from mcp import ClientSession
from mcp.client.sse import sse_client

# Define configuration
MCP_SERVER_URL = "http://localhost:8104/sse"

async def check_server_available(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=2) as response:
                return response.status in (200, 404, 405)
    except:
        return False

@pytest.fixture
async def mcp_session():
    """Fixture that handles MCP session lifeycle"""
    if not await check_server_available(MCP_SERVER_URL):
        pytest.skip(f"Technical Analyst MCP at {MCP_SERVER_URL} is not available. Ensure docker-compose is up.")
    
    async with sse_client(url=MCP_SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session

@pytest.mark.asyncio
async def test_petr4_analysis(mcp_session):
    """Test full analysis for PETR4.SA"""
    print("\n🔍 Testing PETR4.SA Analysis...")
    
    # Analyze ticker
    result = await mcp_session.call_tool("analyze_ticker_full", arguments={"ticker": "PETR4.SA"})
    assert result is not None
    assert len(result.content) > 0
    
    # Parse JSON Result
    data = json.loads(result.content[0].text)
    
    # Basic Validation
    assert "metadata" in data
    assert data["metadata"]["ticker"] == "PETR4.SA"
    assert "momentum" in data
    assert "trend" in data
    assert "volume_confirmation" in data
    
    # Data Integrity
    assert "rsi" in data["momentum"]
    assert "golden_cross" in data["trend"]
    
    print(f"   ✅ PETR4.SA RSI: {data['momentum']['rsi']}")
    print(f"   ✅ PETR4.SA Trend: {data['trend']['price_vs_sma50']}")


@pytest.mark.asyncio
async def test_googl_key_levels(mcp_session):
    """Test key levels for GOOGL"""
    print("\n🔍 Testing GOOGL Key Levels...")
    
    # Get Key Levels
    result = await mcp_session.call_tool("get_key_levels", arguments={"ticker": "GOOGL"})
    assert result is not None
    assert len(result.content) > 0
    
    # Parse JSON Result
    data = json.loads(result.content[0].text)
    
    # Basic Validation
    assert data["ticker"] == "GOOGL"
    assert "major_support" in data
    assert "major_resistance" in data
    assert "distance_to_resistance" in data
    
    print(f"   ✅ GOOGL Support: {data['major_support']}")
    print(f"   ✅ GOOGL Resistance: {data['major_resistance']}")


@pytest.mark.asyncio
async def test_invalid_ticker(mcp_session):
    """Test error handling for invalid ticker"""
    print("\n🔍 Testing Invalid Ticker Handling...")
    
    result = await mcp_session.call_tool("analyze_ticker_full", arguments={"ticker": "INVALID_TICKER_XYZ"})
    assert result is not None
    
    data = json.loads(result.content[0].text)
    assert "error" in data
    error_msg = data["error"]
    print(f"   ✅ Error Handled: {error_msg}")
    
    # Verify the error message is user-friendly and not just a stack trace
    assert "Failed to analyze" in error_msg
    assert "not found or no data available" in error_msg
