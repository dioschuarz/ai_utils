#!/usr/bin/env python3
"""
Example client for connecting to FastMCP servers using SSE transport.

This demonstrates how to connect to your MCP servers from your application.
"""

import asyncio
from typing import Any, Dict

from mcp import ClientSession
from mcp.client.sse import sse_client


async def connect_to_mcp_server(url: str) -> ClientSession:
    """
    Connect to an MCP server using SSE transport.
    
    Args:
        url: Full URL to the MCP server SSE endpoint (e.g., "http://localhost:8100/sse")
        
    Returns:
        ClientSession instance ready to use
    """
    async with sse_client(url=url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return session


async def list_tools(session: ClientSession) -> list[Dict[str, Any]]:
    """List all available tools from the MCP server."""
    response = await session.list_tools()
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema,
        }
        for tool in response.tools
    ]


async def call_tool(
    session: ClientSession, tool_name: str, arguments: Dict[str, Any]
) -> Any:
    """Call a tool on the MCP server."""
    result = await session.call_tool(tool_name, arguments=arguments)
    return result.content


async def example_damodaran_valuation():
    """Example: Connect to Damodaran Valuation MCP server."""
    print("=" * 60)
    print("Damodaran Valuation MCP Server Example")
    print("=" * 60)
    
    url = "http://localhost:8100/sse"
    
    async with sse_client(url=url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List available tools
            print("\n📋 Available Tools:")
            tools = await list_tools(session)
            for tool in tools:
                print(f"  - {tool['name']}: {tool['description']}")
            
            # Example: Get sector metrics
            print("\n🔧 Calling get_sector_metrics('Technology'):")
            result = await call_tool(session, "get_sector_metrics", {"sector_name": "Technology"})
            print(f"Result: {result}")
            
            # Example: Get country risk premium
            print("\n🔧 Calling get_country_risk_premium('Brazil'):")
            result = await call_tool(session, "get_country_risk_premium", {"country": "Brazil"})
            print(f"Result: {result}")


async def example_fundamentus_b3():
    """Example: Connect to Fundamentus B3 MCP server."""
    print("\n" + "=" * 60)
    print("Fundamentus B3 MCP Server Example")
    print("=" * 60)
    
    url = "http://localhost:8101/sse"
    
    async with sse_client(url=url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # List available tools
            print("\n📋 Available Tools:")
            tools = await list_tools(session)
            for tool in tools:
                print(f"  - {tool['name']}: {tool['description']}")
            
            # Example: Get B3 snapshot
            print("\n🔧 Calling get_b3_snapshot('PETR4'):")
            result = await call_tool(session, "get_b3_snapshot", {"ticker": "PETR4"})
            print(f"Result keys: {list(result[0].text.keys()) if result else 'No result'}")
            
            # Example: Get fundamental metrics
            print("\n🔧 Calling get_fundamental_metrics('VALE3'):")
            result = await call_tool(session, "get_fundamental_metrics", {"ticker": "VALE3"})
            print(f"Result: {result}")


class MCPClient:
    """
    Convenient wrapper class for connecting to MCP servers.
    
    Usage:
        async with MCPClient("http://localhost:8100/sse") as client:
            tools = await client.list_tools()
            result = await client.call_tool("tool_name", {"arg": "value"})
    """
    
    def __init__(self, url: str, headers: Dict[str, str] = None):
        """
        Initialize MCP client.
        
        Args:
            url: Full URL to the MCP server SSE endpoint
            headers: Optional HTTP headers
        """
        self.url = url
        self.headers = headers or {}
        self._read = None
        self._write = None
        self._sse_context = None
        self._session = None
    
    async def __aenter__(self):
        """Connect to the MCP server."""
        self._sse_context = sse_client(url=self.url, headers=self.headers)
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
    
    async def list_tools(self) -> list[Dict[str, Any]]:
        """List all available tools."""
        response = await self._session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            }
            for tool in response.tools
        ]
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the MCP server."""
        result = await self._session.call_tool(tool_name, arguments=arguments)
        return result.content


async def example_using_wrapper():
    """Example using the MCPClient wrapper class."""
    print("\n" + "=" * 60)
    print("Using MCPClient Wrapper")
    print("=" * 60)
    
    # Connect to Damodaran server
    async with MCPClient("http://localhost:8100/sse") as client:
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
