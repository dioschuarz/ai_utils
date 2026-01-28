# Alpha-Guardian Technical Analyst MCP

This MCP server provides technical analysis tools for stock tickers using yahoo finance data (`yfinance`) and `pandas_ta`.

## Tools

### `analyze_ticker_full(ticker: str) -> str`
Performs a comprehensive technical analysis over 5 years of data.
Returns a JSON string containing:
- **Momentum**: RSI, MACD signal
- **Trend**: SMA 50/200 crossover (Golden Cross), Price vs SMA50, Bollinger Bands position
- **Volume**: OBV trend, Volume relative to average

### `get_key_levels(ticker: str) -> str`
Identifies major support and resistance levels based on the last 6 months of price action.

## Configuration

The server is configured via environment variables:

- `MCP_HOST`: Host to bind to (default: 0.0.0.0)
- `MCP_PORT`: Port to bind to (default: 8000)

## Running

### Docker
```bash
docker build -t technical-analyst-mcp .
docker run -p 8104:8000 technical-analyst-mcp
```
