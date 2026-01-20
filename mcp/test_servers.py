#!/usr/bin/env python3
"""
Test script for MCP servers.
Tests connection and basic functionality of both servers.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import client_example
sys.path.insert(0, str(Path(__file__).parent))

from mcp import ClientSession
from mcp.client.sse import sse_client


async def test_server(name: str, url: str):
    """Test a single MCP server."""
    print(f"\n{'='*60}")
    print(f"Testing {name}")
    print(f"{'='*60}")
    print(f"Endpoint: {url}\n")
    
    try:
        async with sse_client(url=url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # List tools
                print("📋 Listing available tools...")
                tools_response = await session.list_tools()
                tools = tools_response.tools
                print(f"   Found {len(tools)} tools:")
                for tool in tools:
                    print(f"   - {tool.name}: {tool.description}")
                
                # Test specific tools based on server
                if "damodaran" in name.lower():
                    await test_damodaran_tools(session)
                elif "fundamentus" in name.lower():
                    await test_fundamentus_tools(session)
                elif "yfinance" in name.lower():
                    await test_yfinance_tools(session)
                
                print(f"\n✅ {name} server is working correctly!")
                return True
                
    except Exception as e:
        print(f"\n❌ Error testing {name}: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_damodaran_tools(session: ClientSession):
    """Test Damodaran valuation tools."""
    print("\n🔧 Testing Damodaran tools...")
    
    # Test get_sector_metrics
    print("\n   1. Testing get_sector_metrics('Technology')...")
    try:
        result = await session.call_tool(
            "get_sector_metrics",
            arguments={"sector_name": "Technology"}
        )
        if result.content:
            print(f"      ✅ Success: {result.content[0].text[:200]}...")
        else:
            print("      ⚠️  No content returned")
    except Exception as e:
        print(f"      ❌ Error: {e}")
    
    # Test get_country_risk_premium
    print("\n   2. Testing get_country_risk_premium('Brazil')...")
    try:
        result = await session.call_tool(
            "get_country_risk_premium",
            arguments={"country": "Brazil"}
        )
        if result.content:
            print(f"      ✅ Success: {result.content[0].text[:200]}...")
        else:
            print("      ⚠️  No content returned")
    except Exception as e:
        print(f"      ❌ Error: {e}")


async def test_fundamentus_tools(session: ClientSession):
    """Test Fundamentus B3 tools."""
    print("\n🔧 Testing Fundamentus tools...")
    
    # Test get_b3_snapshot
    print("\n   1. Testing get_b3_snapshot('PETR4')...")
    try:
        result = await session.call_tool(
            "get_b3_snapshot",
            arguments={"ticker": "PETR4"}
        )
        if result.content:
            content_text = result.content[0].text if result.content else ""
            print(f"      ✅ Success: Received data for PETR4")
            if "error" not in content_text.lower():
                print(f"      Data preview: {content_text[:150]}...")
            else:
                print(f"      ⚠️  Response contains error: {content_text[:200]}")
        else:
            print("      ⚠️  No content returned")
    except Exception as e:
        print(f"      ❌ Error: {e}")
    
    # Test search_tickers
    print("\n   2. Testing search_tickers('Petrobras')...")
    try:
        result = await session.call_tool(
            "search_tickers",
            arguments={"query": "Petrobras"}
        )
        if result.content:
            print(f"      ✅ Success: Search completed")
            content_text = result.content[0].text if result.content else ""
            print(f"      Preview: {content_text[:150]}...")
        else:
            print("      ⚠️  No content returned")
    except Exception as e:
        print(f"      ❌ Error: {e}")


async def test_yfinance_tools(session: ClientSession):
    """Test YFinance tools."""
    print("\n🔧 Testing YFinance tools...")
    
    # Test yfinance_get_ticker_info
    print("\n   1. Testing yfinance_get_ticker_info('AAPL')...")
    try:
        result = await session.call_tool(
            "yfinance_get_ticker_info",
            arguments={"symbol": "AAPL"}
        )
        if result.content:
            content_text = result.content[0].text if result.content else ""
            print(f"      ✅ Success: Received data for AAPL")
            if "error" not in content_text.lower():
                print(f"      Data preview: {content_text[:150]}...")
            else:
                print(f"      ⚠️  Response contains error: {content_text[:200]}")
        else:
            print("      ⚠️  No content returned")
    except Exception as e:
        print(f"      ❌ Error: {e}")
    
    # Test yfinance_search
    print("\n   2. Testing yfinance_search('Apple', 'quotes')...")
    try:
        result = await session.call_tool(
            "yfinance_search",
            arguments={"query": "Apple", "search_type": "quotes"}
        )
        if result.content:
            print(f"      ✅ Success: Search completed")
            content_text = result.content[0].text if result.content else ""
            print(f"      Preview: {content_text[:150]}...")
        else:
            print("      ⚠️  No content returned")
    except Exception as e:
        print(f"      ❌ Error: {e}")


async def main():
    """Run tests for all MCP servers."""
    print("="*60)
    print("MCP Servers Test Suite")
    print("="*60)
    
    servers = [
        ("Damodaran Valuation", "http://localhost:8100/sse"),
        ("Fundamentus B3", "http://localhost:8101/sse"),
        ("YFinance", "http://localhost:8102/sse"),
    ]
    
    results = []
    for name, url in servers:
        success = await test_server(name, url)
        results.append((name, success))
    
    # Summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(success for _, success in results)
    if all_passed:
        print("\n🎉 All servers are working correctly!")
        return 0
    else:
        print("\n⚠️  Some servers have issues. Check the logs above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
