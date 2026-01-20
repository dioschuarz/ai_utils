# YFinance MCP Server

FastMCP server exposing Yahoo Finance tools for stock market data, news, and analysis.

## Overview

This MCP server integrates with Yahoo Finance via the `yfinance` library to provide comprehensive financial data including:
- Stock information and financials
- Historical price data with charting capabilities
- News articles and press releases
- Search functionality for stocks, ETFs, and news
- Sector analysis and top performers

## Services

- MCP server (SSE): `http://localhost:8102/sse`

## Environment

Create a `.env` file in this folder with:

```env
MCP_HOST=0.0.0.0
MCP_PORT=8000

# Optional: Web Summarizer MCP configuration (for yfinance_get_ticker_news_summarized)
WEB_SUMMARIZER_URL=http://localhost:8103/sse
WEB_SUMMARIZER_TIMEOUT=60
MAX_NEWS_TO_SUMMARIZE=10
```

**Note:** The `yfinance_get_ticker_news_summarized` tool requires `web_summarizer_mcp` to be running. If not configured or unavailable, the tool will return news without summaries when `fallback_on_error=True`.

## Build and Run (Docker)

1. Ensure the external network exists:

```bash
docker network create investment-net
```

2. Start services:

```bash
docker compose -f /home/ds/projects/ai_utils/mcp/yfinance_mcp/docker-compose.yml up --build
```

Or use the unified docker-compose from the parent directory:

```bash
docker compose -f /home/ds/projects/ai_utils/mcp/docker-compose.yml up -d yfinance-mcp
```

## Tools

The server exposes 6 MCP tools:

### 1. `yfinance_get_ticker_info(symbol: str)`
Retrieve comprehensive stock data including company information, financials, trading metrics and governance.

Returns JSON object with fields including:
- Company: symbol, longName, sector, industry, longBusinessSummary, website, city, country
- Price: currentPrice, previousClose, open, dayHigh, dayLow, fiftyTwoWeekHigh, fiftyTwoWeekLow
- Valuation: marketCap, enterpriseValue, trailingPE, forwardPE, priceToBook, pegRatio
- Trading: volume, averageVolume, averageVolume10days, bid, ask, bidSize, askSize
- Dividends: dividendRate, dividendYield, exDividendDate, payoutRatio
- Financials: totalRevenue, revenueGrowth, earningsGrowth, profitMargins, operatingMargins
- Performance: beta, fiftyDayAverage, twoHundredDayAverage, trailingEps, forwardEps

### 2. `yfinance_get_ticker_news(symbol: str)`
Fetch recent news articles and press releases for a specific stock.

Returns JSON array where each news item includes:
- id: Unique article identifier
- content: Object with title, summary, pubDate, provider, canonicalUrl, thumbnail, contentType

### 2.5. `yfinance_get_ticker_news_summarized(symbol: str, max_news: int = 10, timeout_per_url: int = 30, fallback_on_error: bool = True)`
Get news articles with AI-generated summaries in a single call.

This tool combines `yfinance_get_ticker_news` with `web_summarizer_mcp` to provide comprehensive news analysis with AI-generated summaries using Google Gemini.

**Parameters:**
- `symbol`: Stock ticker symbol (e.g., 'AAPL', 'PETR4.SA')
- `max_news`: Maximum number of news articles to summarize (default: 10, max: 10)
- `timeout_per_url`: Timeout in seconds for each URL crawl and summarization (default: 30, range: 10-120)
- `fallback_on_error`: If True, return news without summaries if summarization fails (default: True)

**Returns JSON object with:**
- `symbol`: Stock ticker symbol
- `news_count`: Total number of news articles found
- `summarized_count`: Number of articles successfully summarized
- `summaries`: Array of news items with their AI-generated summaries
  - `news_item`: Original news article data
  - `summary`: Summary data with status, tokens_used, processing_time_seconds, summary text
- `failed_summaries`: Array of news items that failed summarization (if any)
- `metadata`: Processing statistics (total_news, summarized, failed, total_tokens_used, total_processing_time_seconds)
- `fallback_used`: Boolean indicating if fallback to news-only was used
- `rate_limit_stats`: Rate limiter statistics from web_summarizer_mcp (if available)

**Benefits:**
- Single MCP call instead of two separate calls
- Automatic URL extraction from news
- Fallback to news-only if summarization fails
- Comprehensive error handling

**Dependencies:**
- Requires `web_summarizer_mcp` to be running and accessible
- Configure `WEB_SUMMARIZER_URL` environment variable if using custom setup
  - Default: `http://localhost:8103/sse` (local) or `http://web-summarizer-mcp:8000/sse` (Docker)

**Performance:**
- Typically takes 30-60 seconds for 10 news articles
- If `web_summarizer_mcp` is unavailable and `fallback_on_error=True`, returns news only (fast fallback)
- See comparison tests for detailed performance metrics vs. separate calls

**Example:**
```python
result = await session.call_tool(
    "yfinance_get_ticker_news_summarized",
    arguments={
        "symbol": "PETR4.SA",
        "max_news": 5,
        "timeout_per_url": 30,
        "fallback_on_error": True
    }
)
```

### 3. `yfinance_get_ticker_news_summarized(symbol: str, max_news: int = 10, timeout_per_url: int = 30, fallback_on_error: bool = True)`

See detailed documentation above in section 2.5.

### 4. `yfinance_search(query: str, search_type: SearchType)`
Search Yahoo Finance for stocks, ETFs, and news articles.

Parameters:
- `query`: Company name, ticker symbol, or keywords
- `search_type`: 'all' (quotes + news), 'quotes' (stocks/ETFs only), or 'news' (articles only)

Returns JSON with search results based on search_type.

### 5. `yfinance_get_top(sector: Sector, top_type: TopType, top_n: int = 10)`
Get top-ranked financial entities within a sector.

Parameters:
- `sector`: Market sector (e.g., 'Technology', 'Healthcare', 'Financial Services')
- `top_type`: Type of entities to retrieve:
  - 'top_etfs': Sector ETFs
  - 'top_mutual_funds': Sector mutual funds
  - 'top_companies': Largest by market cap
  - 'top_growth_companies': Fastest revenue/earnings growth
  - 'top_performing_companies': Best stock price performance
- `top_n`: Number of top entities to retrieve (1-100, default: 10)

### 6. `yfinance_get_price_history(symbol: str, period: Period = "1mo", interval: Interval = "1d", chart_type: ChartType | None = None)`
Fetch historical price data and optionally generate technical analysis charts.

Parameters:
- `symbol`: Stock ticker symbol (e.g., 'AAPL', 'GOOGL', 'MSFT')
- `period`: Time range ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
- `interval`: Data granularity ('1m', '5m', '15m', '30m', '1h', '1d', '5d', '1wk', '1mo', '3mo')
- `chart_type`: Optional visualization:
  - 'price_volume': Candlestick chart with volume bars
  - 'vwap': Price with Volume Weighted Average Price overlay
  - 'volume_profile': Volume distribution by price level
  - `None`: Returns Markdown table with OHLCV data

When `chart_type` is None, returns Markdown table. When specified, returns a chart image (WebP format).

## Examples

### Get Apple stock information
```python
result = await session.call_tool(
    "yfinance_get_ticker_info",
    arguments={"symbol": "AAPL"}
)
```

### Search for stocks
```python
result = await session.call_tool(
    "yfinance_search",
    arguments={"query": "Apple", "search_type": "quotes"}
)
```

### Get price history with chart
```python
result = await session.call_tool(
    "yfinance_get_price_history",
    arguments={
        "symbol": "AAPL",
        "period": "1mo",
        "interval": "1d",
        "chart_type": "price_volume"
    }
)
```

## Notes

- No database required: This server uses Yahoo Finance API directly, no PostgreSQL needed
- Rate limiting: Be mindful of API rate limits when making multiple requests
- Data availability: Some data may not be available for all symbols or time periods
- Chart generation: Chart images are returned as base64-encoded WebP format for efficient transmission
