#!/usr/bin/env python3
"""
Comparison test for news summarization flows.

Compares:
1. Current flow: 2 separate MCP calls (yfinance_get_ticker_news + summarize_web)
2. New flow: 1 MCP call (yfinance_get_ticker_news_summarized)

Simulates agent thinking time between calls and measures total time.

Usage:
    python3 mcp/test_news_summarized_comparison.py PETR4.SA 5
"""

import asyncio
import json
import sys
import time
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
        if result.content and len(result.content) > 0:
            return result.content[0].text
        return ""


def extract_urls_from_news(news_data: List[Dict[str, Any]]) -> tuple[List[str], List[str]]:
    """Extract URLs and titles from news data."""
    urls = []
    titles = []

    for item in news_data:
        url = None
        title = None

        if "content" in item and isinstance(item["content"], dict):
            content = item["content"]
            title = content.get("title", "")
            if "canonicalUrl" in content and isinstance(content["canonicalUrl"], dict):
                url = content["canonicalUrl"].get("url")
            elif "clickThroughUrl" in content:
                url = content.get("clickThroughUrl")

        if url and url.startswith(("http://", "https://")):
            urls.append(url)
            titles.append(title if title else None)

    return urls, titles


async def test_current_flow(ticker: str, max_news: int, agent_thinking_time: float = 2.5) -> Dict[str, Any]:
    """Test current flow: 2 separate MCP calls."""
    print(f"\n{'='*70}")
    print(f"Testing CURRENT FLOW (2 separate calls)")
    print(f"{'='*70}")

    start_time = time.time()
    metrics = {
        "flow_type": "current",
        "mcp_calls": 0,
        "agent_thinking_time": 0.0,
        "network_round_trips": 0,
        "steps": [],
    }

    try:
        # Step 1: Agent decides to call yfinance_get_ticker_news
        print(f"\n[Step 1] Agent thinking... ({agent_thinking_time}s)")
        await asyncio.sleep(agent_thinking_time)
        metrics["agent_thinking_time"] += agent_thinking_time
        step_start = time.time()

        # Step 2: Call yfinance_get_ticker_news
        print(f"[Step 2] Calling yfinance_get_ticker_news('{ticker}')...")
        async with MCPClient("http://localhost:8102/sse") as client:
            metrics["mcp_calls"] += 1
            metrics["network_round_trips"] += 1
            news_result = await client.call_tool(
                "yfinance_get_ticker_news",
                arguments={"symbol": ticker},
            )
            step_time = time.time() - step_start
            metrics["steps"].append({"name": "get_news", "time": step_time})

        news_data = json.loads(news_result)
        if isinstance(news_data, dict) and "error" in news_data:
            print(f"❌ Error getting news: {news_data.get('error')}")
            return metrics

        print(f"✓ Retrieved {len(news_data)} news articles ({step_time:.2f}s)")

        # Step 3: Extract URLs
        print(f"[Step 3] Extracting URLs...")
        urls, titles = extract_urls_from_news(news_data)
        print(f"✓ Extracted {len(urls)} URLs")

        if not urls:
            print("❌ No URLs found")
            return metrics

        # Step 4: Agent decides to call summarize_web
        print(f"\n[Step 4] Agent thinking... ({agent_thinking_time}s)")
        await asyncio.sleep(agent_thinking_time)
        metrics["agent_thinking_time"] += agent_thinking_time
        step_start = time.time()

        # Step 5: Call summarize_web
        print(f"[Step 5] Calling summarize_web with {min(len(urls), max_news)} URLs...")
        async with MCPClient("http://localhost:8103/sse") as client:
            metrics["mcp_calls"] += 1
            metrics["network_round_trips"] += 1
            summary_result = await client.call_tool(
                "summarize_web",
                arguments={
                    "urls": urls[:max_news],
                    "titles": titles[:max_news] if titles else None,
                    "max_urls": max_news,
                    "timeout_per_url": 30,
                },
            )
            step_time = time.time() - step_start
            metrics["steps"].append({"name": "summarize", "time": step_time})

        summary_data = json.loads(summary_result)
        if isinstance(summary_data, dict) and "error" in summary_data:
            print(f"❌ Error summarizing: {summary_data.get('error')}")
            return metrics

        metadata = summary_data.get("metadata", {})
        print(f"✓ Summarized {metadata.get('total_succeeded', 0)} articles ({step_time:.2f}s)")

        metrics["total_time"] = time.time() - start_time
        metrics["success"] = True
        metrics["tokens_used"] = metadata.get("total_tokens_used", 0)
        metrics["summarized_count"] = metadata.get("total_succeeded", 0)

        return metrics

    except Exception as e:
        print(f"❌ Error in current flow: {e}")
        import traceback
        traceback.print_exc()
        metrics["total_time"] = time.time() - start_time
        metrics["success"] = False
        metrics["error"] = str(e)
        return metrics


async def test_new_flow(ticker: str, max_news: int, agent_thinking_time: float = 2.5) -> Dict[str, Any]:
    """Test new flow: 1 MCP call with wrapper."""
    print(f"\n{'='*70}")
    print(f"Testing NEW FLOW (1 call with wrapper)")
    print(f"{'='*70}")

    start_time = time.time()
    metrics = {
        "flow_type": "new",
        "mcp_calls": 0,
        "agent_thinking_time": 0.0,
        "network_round_trips": 0,
        "steps": [],
    }

    try:
        # Step 1: Agent decides to call yfinance_get_ticker_news_summarized
        print(f"\n[Step 1] Agent thinking... ({agent_thinking_time}s)")
        await asyncio.sleep(agent_thinking_time)
        metrics["agent_thinking_time"] += agent_thinking_time
        step_start = time.time()

        # Step 2: Call yfinance_get_ticker_news_summarized (does everything internally)
        print(f"[Step 2] Calling yfinance_get_ticker_news_summarized('{ticker}', max_news={max_news})...")
        async with MCPClient("http://localhost:8102/sse") as client:
            metrics["mcp_calls"] += 1
            metrics["network_round_trips"] += 1
            result = await client.call_tool(
                "yfinance_get_ticker_news_summarized",
                arguments={
                    "symbol": ticker,
                    "max_news": max_news,
                    "timeout_per_url": 30,
                    "fallback_on_error": True,
                },
            )
            step_time = time.time() - step_start
            metrics["steps"].append({"name": "get_news_summarized", "time": step_time})

        result_data = json.loads(result)
        if isinstance(result_data, dict) and "error" in result_data:
            print(f"❌ Error: {result_data.get('error')}")
            return metrics

        metadata = result_data.get("metadata", {})
        print(f"✓ Retrieved and summarized {metadata.get('summarized', 0)} articles ({step_time:.2f}s)")

        metrics["total_time"] = time.time() - start_time
        metrics["success"] = True
        metrics["tokens_used"] = metadata.get("total_tokens_used", 0)
        metrics["summarized_count"] = metadata.get("summarized", 0)

        return metrics

    except Exception as e:
        print(f"❌ Error in new flow: {e}")
        import traceback
        traceback.print_exc()
        metrics["total_time"] = time.time() - start_time
        metrics["success"] = False
        metrics["error"] = str(e)
        return metrics


def print_comparison(current_metrics: Dict[str, Any], new_metrics: Dict[str, Any]) -> None:
    """Print comparison of metrics."""
    print(f"\n{'='*70}")
    print(f"COMPARISON RESULTS")
    print(f"{'='*70}")

    print(f"\n📊 Metrics Comparison:")
    print(f"{'-'*70}")

    # Total time
    current_time = current_metrics.get("total_time", 0)
    new_time = new_metrics.get("total_time", 0)
    time_diff = current_time - new_time
    time_percent = (time_diff / current_time * 100) if current_time > 0 else 0

    print(f"\n⏱️  Total Time:")
    print(f"  Current flow: {current_time:.2f}s")
    print(f"  New flow:     {new_time:.2f}s")
    print(f"  Difference:   {time_diff:+.2f}s ({time_percent:+.1f}%)")

    # MCP calls
    current_calls = current_metrics.get("mcp_calls", 0)
    new_calls = new_metrics.get("mcp_calls", 0)
    print(f"\n📞 MCP Calls:")
    print(f"  Current flow: {current_calls} calls")
    print(f"  New flow:     {new_calls} calls")
    print(f"  Reduction:    {current_calls - new_calls} calls ({(1 - new_calls/current_calls)*100:.1f}% reduction)")

    # Network round trips
    current_round_trips = current_metrics.get("network_round_trips", 0)
    new_round_trips = new_metrics.get("network_round_trips", 0)
    print(f"\n🌐 Network Round Trips:")
    print(f"  Current flow: {current_round_trips} round-trips")
    print(f"  New flow:     {new_round_trips} round-trips")
    print(f"  Reduction:    {current_round_trips - new_round_trips} round-trips")

    # Agent thinking time
    current_thinking = current_metrics.get("agent_thinking_time", 0)
    new_thinking = new_metrics.get("agent_thinking_time", 0)
    thinking_diff = current_thinking - new_thinking
    print(f"\n🤔 Agent Thinking Time:")
    print(f"  Current flow: {current_thinking:.2f}s")
    print(f"  New flow:     {new_thinking:.2f}s")
    print(f"  Saved:        {thinking_diff:.2f}s")

    # Tokens used
    current_tokens = current_metrics.get("tokens_used", 0)
    new_tokens = new_metrics.get("tokens_used", 0)
    print(f"\n🎯 Tokens Used:")
    print(f"  Current flow: {current_tokens:,} tokens")
    print(f"  New flow:     {new_tokens:,} tokens")
    if current_tokens > 0 and new_tokens > 0:
        token_diff = abs(current_tokens - new_tokens)
        print(f"  Difference:   {token_diff:,} tokens ({abs(token_diff/max(current_tokens, new_tokens)*100):.1f}%)")

    # Success rate
    current_success = current_metrics.get("success", False)
    new_success = new_metrics.get("success", False)
    print(f"\n✅ Success:")
    print(f"  Current flow: {'✓' if current_success else '✗'}")
    print(f"  New flow:     {'✓' if new_success else '✗'}")

    # Summarized count
    current_count = current_metrics.get("summarized_count", 0)
    new_count = new_metrics.get("summarized_count", 0)
    print(f"\n📰 Summarized Articles:")
    print(f"  Current flow: {current_count} articles")
    print(f"  New flow:     {new_count} articles")

    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    if time_diff > 0:
        print(f"✅ New flow is {time_diff:.2f}s faster ({time_percent:.1f}% improvement)")
        print(f"✅ Reduced from {current_calls} to {new_calls} MCP calls")
        print(f"✅ Saved {thinking_diff:.2f}s of agent thinking time")
    else:
        print(f"⚠️  New flow is {abs(time_diff):.2f}s slower")
        print(f"   (This may be due to network conditions or processing variations)")


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python3 test_news_summarized_comparison.py <TICKER> [MAX_NEWS] [AGENT_THINKING_TIME]")
        print("Example: python3 test_news_summarized_comparison.py PETR4.SA 5 2.5")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    max_news = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    agent_thinking_time = float(sys.argv[3]) if len(sys.argv) > 3 else 2.5

    print(f"\n{'#'*70}")
    print(f"# News Summarization Flow Comparison")
    print(f"{'#'*70}")
    print(f"Ticker: {ticker}")
    print(f"Max News: {max_news}")
    print(f"Agent Thinking Time: {agent_thinking_time}s per decision")
    print(f"\n⚠️  Make sure both MCP servers are running:")
    print(f"   - yfinance_mcp: http://localhost:8102/sse")
    print(f"   - web_summarizer_mcp: http://localhost:8103/sse")
    print()

    # Run both tests
    current_metrics = await test_current_flow(ticker, max_news, agent_thinking_time)

    # Wait a bit between tests
    print(f"\n⏳ Waiting 5 seconds before next test...")
    await asyncio.sleep(5)

    new_metrics = await test_new_flow(ticker, max_news, agent_thinking_time)

    # Compare results
    if current_metrics.get("success") and new_metrics.get("success"):
        print_comparison(current_metrics, new_metrics)
    else:
        print(f"\n⚠️  One or both tests failed. Cannot compare.")
        if not current_metrics.get("success"):
            print(f"Current flow error: {current_metrics.get('error', 'Unknown')}")
        if not new_metrics.get("success"):
            print(f"New flow error: {new_metrics.get('error', 'Unknown')}")

    print(f"\n{'#'*70}")
    print(f"# Test Complete")
    print(f"{'#'*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
