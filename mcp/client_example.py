#!/usr/bin/env python3
"""
Example client for connecting to FastMCP servers using HTTP transport.

This demonstrates how to connect to your MCP servers from your application
using the FastMCP v3 client.
"""

import asyncio
import os
from typing import Any, Dict, List

from fastmcp.client import Client
from mcp.types import Tool


async def list_tools(client: Client) -> List[Dict[str, Any]]:
    """List all available tools from the MCP server."""
    tools = await client.list_tools()
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema,
        }
        for tool in tools
    ]


async def call_tool(
    client: Client, tool_name: str, arguments: Dict[str, Any]
) -> Any:
    """Call a tool on the MCP server."""
    result = await client.call_tool(tool_name, arguments=arguments)
    return result


async def example_damodaran_valuation():
    """Example: Connect to Damodaran Valuation MCP server."""
    print("=" * 60)
    print("Damodaran Valuation MCP Server Example")
    print("=" * 60)
    
    # FastMCP v3 uses the /mcp path by default for HTTP transport
    url = "http://localhost:8100/mcp"
    
    async with Client(url, name="example-client") as client:
        # List available tools
        print("\n📋 Available Tools:")
        tools = await list_tools(client)
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
        
        # Example: Get sector metrics
        print("\n🔧 Calling get_sector_metrics('Technology'):")
        result = await client.call_tool("get_sector_metrics", {"sector_name": "Technology"})
        print(f"Result: {result}")


async def example_fundamentus_b3():
    """Example: Connect to Fundamentus B3 MCP server."""
    print("\n" + "=" * 60)
    print("Fundamentus B3 MCP Server Example")
    print("=" * 60)
    
    url = "http://localhost:8101/mcp"
    
    async with Client(url, name="example-client") as client:
        # List available tools
        print("\n📋 Available Tools:")
        tools = await list_tools(client)
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
        
        # Example: Get B3 snapshot
        print("\n🔧 Calling get_b3_snapshot('PETR4'):")
        result = await client.call_tool("get_b3_snapshot", {"ticker": "PETR4"})
        print(f"Result: {result}")


class MCPClient:
    """
    Convenient wrapper class for connecting to MCP servers.
    """
    
    def __init__(self, url: str, headers: Dict[str, str] = None):
        """
        Initialize MCP client.
        """
        # Ensure /mcp is present
        if not url.endswith("/mcp"):
            url = url.replace("/sse", "").rstrip("/") + "/mcp"
        self.url = url
        self.headers = headers or {}
        self._client = None
    
    async def __aenter__(self):
        """Connect to the MCP server."""
        self._client = Client(self.url, name="mcp-wrapper-client")
        await self._client.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Disconnect from the MCP server."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
        self._client = None
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools."""
        tools = await self._client.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            }
            for tool in tools
        ]
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the MCP server."""
        return await self._client.call_tool(tool_name, arguments=arguments)


async def example_using_wrapper():
    """Example using the MCPClient wrapper class."""
    print("\n" + "=" * 60)
    print("Using MCPClient Wrapper")
    print("=" * 60)
    
    async with MCPClient("http://localhost:8100/mcp") as client:
        tools = await client.list_tools()
        print(f"\nFound {len(tools)} tools")
        
        # Call a tool
        result = await client.call_tool(
            "calculate_levered_beta",
            {"sector_name": "Technology", "current_de_ratio": 0.5}
        )
        print(f"\nLevered Beta Result: {result}")


async def main():
    """Run all examples."""
    try:
        await example_damodaran_valuation()
        await example_fundamentus_b3()
        await example_using_wrapper()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure the MCP servers are running:")
        print("  python3 mcp/manage_mcp_servers.py start")


if __name__ == "__main__":
    asyncio.run(main())
