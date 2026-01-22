import asyncio
import json
from mcp import ClientSession
from mcp.client.sse import sse_client

async def test_call():
    url = "http://localhost:8102/sse"
    try:
        async with sse_client(url=url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                print("Calling with 'ticker' (expecting error):")
                try:
                    result = await session.call_tool("yfinance_get_ticker_news_summarized", arguments={"ticker": "VALE3"})
                    print(f"Result: {result}")
                except Exception as e:
                    print(f"Error: {e}")

                print("\nCalling with 'symbol' (expecting success):")
                try:
                    result = await session.call_tool("yfinance_get_ticker_news_summarized", arguments={"symbol": "VALE3", "max_news": 2})
                    print(f"Result: {result}")
                except Exception as e:
                    print(f"Error: {e}")

    except Exception as e:
        print(f"Connection Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_call())
