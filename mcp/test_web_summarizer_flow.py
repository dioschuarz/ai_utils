#!/usr/bin/env python3
"""
Test script for Web Summarizer MCP flow.

Simulates the complete agent flow:
1. Get news from yfinance_mcp for a ticker
2. Extract URLs from news
3. Summarize using web_summarizer_mcp
4. Display results

Usage:
    python3 mcp/test_web_summarizer_flow.py PETR4.SA
"""

import asyncio
import json
import sys
from typing import Any, Dict, List

from mcp import ClientSession
from mcp.client.sse import sse_client


class MCPClient:
    """Convenient wrapper for MCP server connections."""

    def __init__(self, url: str):
        self.url = url
        self._read = None
        self._write = None
        self._sse_context = None
        self._session = None

    async def __aenter__(self):
        """Connect to the MCP server."""
        self._sse_context = sse_client(url=self.url)
        self._read, self._write = await self._sse_context.__aenter__()

        session_ctx = ClientSession(self._read, self._write)
        self._session = await session_ctx.__aenter__()
        await self._session.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Disconnect from the MCP server."""
        if self._session:
            await self._session.__aexit__(exc_type, exc_val, exc_tb)
        if self._sse_context:
            await self._sse_context.__aexit__(exc_type, exc_val, exc_tb)
        self._session = None
        self._read = None
        self._write = None
        self._sse_context = None

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on the MCP server."""
        result = await self._session.call_tool(tool_name, arguments=arguments)
        # Extract text from MCP response
        if result.content and len(result.content) > 0:
            return result.content[0].text
        return ""


async def get_ticker_news(ticker: str) -> List[Dict[str, Any]]:
    """Get news for a ticker from yfinance_mcp."""
    print(f"\n{'='*70}")
    print(f"Step 1: Getting news for {ticker} from yfinance_mcp")
    print(f"{'='*70}")

    async with MCPClient("http://localhost:8102/sse") as client:
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

    async with MCPClient("http://localhost:8103/sse") as client:
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
    print(f"\n{'='*70}")
    print(f"Results Summary")
    print(f"{'='*70}")

    if not summary_data:
        print("❌ No summary data available")
        return

    metadata = summary_data.get("metadata", {})
    summaries = summary_data.get("summaries", [])
    errors = summary_data.get("errors", [])

    print(f"\n📊 Processing Statistics:")
    print(f"  Total news articles: {len(news_data)}")
    print(f"  URLs requested: {metadata.get('total_requested', 0)}")
    print(f"  URLs processed: {metadata.get('total_processed', 0)}")
    print(f"  ✓ Successful: {metadata.get('total_succeeded', 0)}")
    print(f"  ⚠️  Partial: {metadata.get('total_partial', 0)}")
    print(f"  ❌ Failed: {metadata.get('total_failed', 0)}")
    print(f"  Total tokens used: {metadata.get('total_tokens_used', 0):,}")
    print(f"  Total time: {metadata.get('total_processing_time_seconds', 0):.1f}s")

    # Rate limit stats
    rate_stats = summary_data.get("rate_limit_stats", {})
    if rate_stats:
        print(f"\n📈 Rate Limit Status:")
        print(f"  Tokens: {rate_stats.get('tokens_used', 0):,} / {rate_stats.get('tokens_limit', 0):,} ({rate_stats.get('tokens_percent', 0):.1f}%)")
        print(f"  Requests: {rate_stats.get('requests_used', 0)} / {rate_stats.get('requests_limit', 0)} ({rate_stats.get('requests_percent', 0):.1f}%)")

    # Display successful summaries
    successful = [s for s in summaries if s.get("status") == "success"]
    if successful:
        print(f"\n✅ Successful Summaries ({len(successful)}):")
        print(f"{'-'*70}")
        for i, summary in enumerate(successful, 1):
            print(f"\n{i}. {summary.get('title', 'No title') or summary.get('url', 'Unknown')[:60]}")
            print(f"   URL: {summary.get('url', '')[:80]}...")
            print(f"   Tokens: {summary.get('tokens_used', 0):,} | Time: {summary.get('processing_time_seconds', 0):.1f}s")
            print(f"   Summary: {summary.get('summary', '')[:200]}...")
            print()

    # Display partial summaries
    partial = [s for s in summaries if s.get("status") == "partial"]
    if partial:
        print(f"\n⚠️  Partial Summaries ({len(partial)}):")
        print(f"{'-'*70}")
        for i, summary in enumerate(partial, 1):
            print(f"\n{i}. {summary.get('title', 'No title') or summary.get('url', 'Unknown')[:60]}")
            print(f"   URL: {summary.get('url', '')[:80]}...")
            print(f"   Error: {summary.get('error', 'Unknown error')}")
            print(f"   Note: {summary.get('note', '')}")
            print()

    # Display errors
    if errors:
        print(f"\n❌ Errors ({len(errors)}):")
        print(f"{'-'*70}")
        for i, error in enumerate(errors, 1):
            print(f"{i}. {error.get('url', 'Unknown')[:80]}")
            print(f"   Error: {error.get('error', 'Unknown')}")
            print(f"   Code: {error.get('error_code', 'UNKNOWN')}")
            print()


async def test_complete_flow(ticker: str, max_news: int = 10) -> None:
    """Test the complete flow: get news -> extract URLs -> summarize."""
    print(f"\n{'#'*70}")
    print(f"# Testing Web Summarizer Flow for {ticker}")
    print(f"{'#'*70}")

    try:
        # Step 1: Get news from yfinance
        news_data = await get_ticker_news(ticker)

        if not news_data:
            print(f"\n❌ No news data available. Cannot proceed.")
            return

        # Step 2: Extract URLs and titles
        urls, titles = extract_urls_and_titles(news_data)

        if not urls:
            print(f"\n❌ No valid URLs found. Cannot proceed.")
            return

        # Step 3: Summarize URLs
        summary_data = await summarize_urls(urls, titles, max_urls=max_news)

        # Step 4: Display results
        display_results(news_data, summary_data)

        print(f"\n{'#'*70}")
        print(f"# Test Complete")
        print(f"{'#'*70}\n")

    except KeyboardInterrupt:
        print(f"\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 test_web_summarizer_flow.py <TICKER> [MAX_NEWS]")
        print("Example: python3 test_web_summarizer_flow.py PETR4.SA 5")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    max_news = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    print("\n⚠️  Make sure both MCP servers are running:")
    print("   - yfinance_mcp: http://localhost:8102/sse")
    print("   - web_summarizer_mcp: http://localhost:8103/sse")
    print("\n   Start with: python3 mcp/manage_mcp_servers.py start --unified")
    print()

    await test_complete_flow(ticker, max_news=max_news)


if __name__ == "__main__":
    asyncio.run(main())
