import asyncio

from src.server import get_ticker_info, search, get_top, get_price_history

async def run_checks():
    print("Testing get_ticker_info...")
    info = await get_ticker_info("AAPL")
    if "error" in info.lower() and "network" not in info.lower():
        print(f"Error in info: {info}")
    else:
        print("get_ticker_info passed (or returned expected output)")

    print("Testing search...")
    s = await search("Apple", "quotes")
    if "error" in s.lower() and "network" not in s.lower():
        print(f"Error in search: {s}")
    else:
        print("search passed")
        
    print("Testing get_top...")
    top = await get_top("Technology", "top_companies", 2)
    if "error" in top.lower() and "network" not in top.lower():
        print(f"Error in get_top: {top}")
    else:
        print("get_top passed")
        
    print("Testing get_price_history...")
    hist = await get_price_history("AAPL", "1mo", "1d", None)
    if isinstance(hist, str) and "error" in hist.lower() and "network" not in hist.lower():
        print(f"Error in get_price_history: {hist}")
    else:
        print("get_price_history passed")
        
if __name__ == "__main__":
    asyncio.run(run_checks())
