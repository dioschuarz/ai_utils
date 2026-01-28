#!/usr/bin/env python3
"""
Test script for MCP servers.
Tests connection and basic functionality of both servers using pytest.
"""

import sys
from pathlib import Path

# Add parent directory to path to import client_example
sys.path.insert(0, str(Path(__file__).parent))

import pytest
import aiohttp
from mcp import ClientSession
from mcp.client.sse import sse_client

SERVERS = [
    ("Damodaran Valuation", "http://localhost:8100/sse", "get_sector_metrics", {"sector_name": "Technology"}),
    ("Fundamentus B3", "http://localhost:8101/sse", "get_b3_snapshot", {"ticker": "PETR4"}),
    ("YFinance", "http://localhost:8102/sse", "yfinance_get_ticker_info", {"symbol": "AAPL"}),
    ("Technical Analyst", "http://localhost:8104/sse", "analyze_ticker_full", {"ticker": "MSFT"}),
]

async def check_server_available(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=2) as response:
                return response.status in (200, 404, 405) # 404/405 usually mean server is up but endpoint expects POST/SSE upgrade
    except:
        return False

@pytest.mark.asyncio
@pytest.mark.parametrize("name, url, test_tool, test_args", SERVERS)
async def test_server_connection(name, url, test_tool, test_args):
    """Test connection and basic tool listing for an MCP server."""
    
    # Skip if server is not reachable
    if not await check_server_available(url):
        pytest.skip(f"{name} server at {url} is not available. Ensure docker-compose is up.")

    print(f"\n{'='*60}")
    print(f"Testing {name}")
    print(f"Endpoint: {url}")

    async with sse_client(url=url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List tools
            print("📋 Listing available tools...")
            tools_response = await session.list_tools()
            tools = tools_response.tools
            assert len(tools) > 0, f"No tools found for {name}"
            
            print(f"   Found {len(tools)} tools")
            tool_names = [t.name for t in tools]
            assert test_tool in tool_names, f"Tool {test_tool} not found in {name}"

            # Test specific tool execution
            print(f"🔧 Testing {test_tool}...")
            result = await session.call_tool(test_tool, arguments=test_args)
            
            assert result is not None
            if result.content:
                print(f"   ✅ Success: {result.content[0].text[:100]}...")
            else:
                print("   ⚠️  No content returned, but call succeeded")
