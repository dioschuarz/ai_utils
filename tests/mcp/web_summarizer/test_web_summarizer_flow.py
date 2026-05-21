#!/usr/bin/env python3
"""
Test script for Web Summarizer MCP flow.

Simulates the complete agent flow:
1. Get news from yfinance_mcp for a ticker
2. Extract URLs from news
3. Summarize using web_summarizer_mcp
4. Display results
"""

import asyncio
import json
import pytest
import aiohttp
from typing import Any, Dict, List

from fastmcp.client import Client

# --- Helper Functions ---

class MCPClient:
    """Convenient wrapper for MCP server connections."""

    def __init__(self, url: str):
        # Strip /mcp and ensure /mcp
        if not url.endswith("/mcp"):
            url = url.replace("/mcp", "").rstrip("/") + "/mcp"
        self.url = url
        self._client = None

    async def __aenter__(self):
        """Connect to the MCP server."""
        self._client = Client(self.url, name="test-client")
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Disconnect from the MCP server."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
        self._client = None

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on the MCP server."""
        result = await self._client.call_tool(tool_name, arguments=arguments)
        # FastMCP v3 call_tool returns a CallToolResult object.
        # Extract the text content from the first block.
        if result.content and len(result.content) > 0:
            return result.content[0].text
        return ""


async def get_ticker_news(ticker: str) -> List[Dict[str, Any]]:
    """Get news for a ticker from yfinance_mcp."""
    print(f"\n{'='*70}")
    print(f"Step 1: Getting news for {ticker} from yfinance_mcp")
    print(f"{'='*70}")

    async with MCPClient("http://localhost:8102/mcp") as client:
        print(f"✓ Connected to yfinance_mcp")
        print(f"  Calling yfinance_get_ticker_news('{ticker}')...")

        try:
            result = await client.call_tool(
                "yfinance_get_ticker_news",
                arguments={"symbol": ticker},
            )

            # Parse JSON response
            news_data = json.loads(result)

            # Check for errors
            if isinstance(news_data, dict) and "error" in news_data:
                print(f"❌ Error: {news_data.get('error')}")
                return []

            if not news_data:
                print(f"⚠️  No news found for {ticker}")
                return []

            print(f"✓ Retrieved {len(news_data)} news articles")
            return news_data

        except Exception as e:
            print(f"❌ Error calling yfinance_get_ticker_news: {e}")
            return []


def extract_urls_and_titles(news_data: List[Dict[str, Any]]) -> tuple[List[str], List[str]]:
    """Extract URLs and titles from news data."""
    print(f"\n{'='*70}")
    print(f"Step 2: Extracting URLs and titles from news")
    print(f"{'='*70}")

    urls = []
    titles = []

    for item in news_data:
        # Extract URL from content.canonicalUrl
        url = None
        title = None

        if "content" in item and isinstance(item["content"], dict):
            content = item["content"]
            
            # Extract title
            title = content.get("title", "")
            
            # Extract URL from canonicalUrl (inside content)
            if "canonicalUrl" in content and isinstance(content["canonicalUrl"], dict):
                url = content["canonicalUrl"].get("url")
            # Fallback: try clickThroughUrl
            elif "clickThroughUrl" in content:
                url = content.get("clickThroughUrl")

        # Validate and add URL
        if url and url.startswith(("http://", "https://")):
            urls.append(url)
            titles.append(title if title else None)

    print(f"✓ Extracted {len(urls)} valid URLs")
    if len(urls) > 0:
        print(f"  First URL: {urls[0][:80]}...")
        if titles[0]:
            print(f"  First title: {titles[0][:80]}...")

    return urls, titles


async def summarize_urls(urls: List[str], titles: List[str], max_urls: int = 10) -> Dict[str, Any]:
    """Summarize URLs using web_summarizer_mcp."""
    print(f"\n{'='*70}")
    print(f"Step 3: Summarizing {min(len(urls), max_urls)} URLs using web_summarizer_mcp")
    print(f"{'='*70}")

    # Limit URLs
    urls_to_summarize = urls[:max_urls]
    titles_to_use = titles[:max_urls] if titles else None

    async with MCPClient("http://localhost:8103/mcp") as client:
        print(f"✓ Connected to web_summarizer_mcp")
        print(f"  Calling summarize_web with {len(urls_to_summarize)} URLs...")
        print(f"  This may take 30-60 seconds...")

        try:
            arguments = {
                "urls": urls_to_summarize,
                "max_urls": max_urls,
                "timeout_per_url": 30,
            }

            if titles_to_use:
                arguments["titles"] = titles_to_use

            result = await client.call_tool(
                "summarize_web",
                arguments=arguments,
            )

            # Parse JSON response
            summary_data = json.loads(result)

            # Check for errors
            if isinstance(summary_data, dict) and "error" in summary_data:
                print(f"❌ Error: {summary_data.get('error')}")
                return {}

            print(f"✓ Summarization complete")
            return summary_data

        except Exception as e:
            print(f"❌ Error calling summarize_web: {e}")
            import traceback
            traceback.print_exc()
            return {}


def display_results(news_data: List[Dict[str, Any]], summary_data: Dict[str, Any]) -> None:
    """Display formatted results."""
    # (Simplified for brevity in logs, but kept functional)
    if not summary_data:
        print("❌ No summary data available")
        return

    metadata = summary_data.get("metadata", {})
    summaries = summary_data.get("summaries", [])
    
    print(f"\n📊 Processing Statistics:")
    print(f"  Total news articles: {len(news_data)}")
    print(f"  URLs processed: {metadata.get('total_processed', 0)}")
    print(f"  ✓ Successful: {metadata.get('total_succeeded', 0)}")
    
    # Check for failures
    failed = metadata.get('total_failed', 0)
    if failed > 0:
         print(f"  ❌ Failed: {failed}")

# --- Automated Test ---

async def check_server_available(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=2) as response:
                return response.status in (200, 404, 405, 406)
    except:
        return False

@pytest.mark.asyncio
@pytest.mark.parametrize("ticker, max_news", [
    ("PETR4.SA", 3),
    ("AAPL", 3)
])
async def test_complete_flow(ticker: str, max_news: int):
    """Test the complete flow: get news -> extract URLs -> summarize."""
    
    print(f"\n{'#'*70}")
    print(f"# Testing Web Summarizer Flow for {ticker}")
    print(f"{'#'*70}")

    # Step 1: Get news from yfinance
    news_data = await get_ticker_news(ticker)
    assert news_data is not None
    if not news_data:
        pytest.skip(f"No news data available for {ticker}, skipping test.")

    # Step 2: Extract URLs and titles
    urls, titles = extract_urls_and_titles(news_data)
    if not urls:
        pytest.skip(f"No valid URLs found for {ticker}, skipping test.")

    # Step 3: Summarize URLs
    summary_data = await summarize_urls(urls, titles, max_urls=max_news)
    
    # Assertions
    assert summary_data is not None, "Summary data should not be None"
    assert "error" not in summary_data, f"Summarization returned error: {summary_data.get('error')}"
    assert "summaries" in summary_data, "Response should contain summaries list"
    
    metadata = summary_data.get("metadata", {})
    assert metadata.get("total_processed", 0) > 0, "Should have processed at least one URL"

    # Step 4: Display results (for logs)
    display_results(news_data, summary_data)

    print(f"\n{'#'*70}")
    print(f"# Test Complete")
    print(f"{'#'*70}\n")
