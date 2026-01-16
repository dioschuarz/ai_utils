# Fundamentus MCP Server

FastMCP server exposing Fundamentus B3 stock data tools with PostgreSQL caching.

## Overview

This MCP server integrates with the `fundamentus` library to provide fundamental data for Brazilian B3 stock market assets. It includes a caching layer using PostgreSQL to optimize API calls and reduce dependency on external scraping.

## Services

- MCP server (SSE): `http://localhost:8101` (host) → `8000` (container)
- Postgres (host): `localhost:5434` → container `5432`

## Environment

Create a `.env` file in this folder with:

```env
MCP_HOST=0.0.0.0
MCP_PORT=8000

POSTGRES_HOST=fundamentus-db
POSTGRES_PORT=5432
POSTGRES_DB=fundamentus
POSTGRES_USER=fundamentus
POSTGRES_PASSWORD=fundamentus
POSTGRES_SSLMODE=disable

CACHE_TTL_HOURS=24
```

## Build and Run (Docker)

1. Ensure the external network exists:

```bash
docker network create investment-net
```

2. Start services:

```bash
docker compose -f /home/ds/projects/ai_utils/mcp/fundamentus_b3/docker-compose.yml up --build
```

## Tools

The server exposes 6 MCP tools:

### 1. `get_b3_snapshot(ticker: str)`

Get a complete snapshot of a B3 stock ticker. Uses cache if available and valid, otherwise fetches from Fundamentus and caches the result.

**Example:**
```python
get_b3_snapshot("PETR4")
```

**Returns:**
```json
{
  "ticker": "PETR4",
  "data": {
    "ticker": "PETR4",
    "cotacao": 32.45,
    "pl": 5.2,
    "dy": 0.12,
    ...
  },
  "source": "cache" | "fundamentus"
}
```

### 2. `get_b3_snapshots(tickers: list[str])`

Get snapshots for multiple B3 stock tickers in batch. Optimizes queries by checking cache first, then fetching from Fundamentus only for cache misses.

**Example:**
```python
get_b3_snapshots(["PETR4", "VALE3", "ITUB4"])
```

**Returns:**
```json
{
  "results": {
    "PETR4": {"data": {...}, "source": "cache"},
    "VALE3": {"data": {...}, "source": "fundamentus"},
    "ITUB4": {"data": {...}, "source": "cache"}
  },
  "summary": {
    "total": 3,
    "cache_hits": 2,
    "cache_misses": 1
  }
}
```

### 3. `get_fundamental_metrics(ticker: str)`

Get essential fundamental metrics for a B3 stock ticker. Extracts key metrics: D/E Ratio, Interest Coverage Ratio (ICR), P/L, DY, ROIC, Margens.

**Example:**
```python
get_fundamental_metrics("PETR4")
```

**Returns:**
```json
{
  "ticker": "PETR4",
  "cotacao": 32.45,
  "p_l": 5.2,
  "dy": 0.12,
  "debt_to_equity": 0.45,
  "interest_coverage": 8.3,
  "roic": 0.15,
  "roe": 0.18,
  "operating_margin": 0.25,
  "net_margin": 0.12
}
```

### 4. `search_tickers(query: str)`

Search for B3 stock tickers by name or segment.

**Example:**
```python
search_tickers("Petrobras")
```

**Returns:**
```json
{
  "query": "Petrobras",
  "count": 2,
  "tickers": [
    {"ticker": "PETR3", "raw_data": {...}},
    {"ticker": "PETR4", "raw_data": {...}}
  ]
}
```

### 5. `refresh_cache(ticker: str)`

Force refresh of cached data for a ticker, ignoring TTL. Useful for critical data that needs to be up-to-date.

**Example:**
```python
refresh_cache("PETR4")
```

### 6. `list_cached_tickers()`

List all tickers that have valid (non-expired) cache entries. Useful for debugging and monitoring.

**Example:**
```python
list_cached_tickers()
```

**Returns:**
```json
{
  "count": 150,
  "tickers": ["PETR4", "VALE3", "ITUB4", ...]
}
```

## Cache Management

The server implements a TTL-based caching system:

- **Default TTL**: 24 hours (configurable via `CACHE_TTL_HOURS`)
- **Automatic expiration**: Expired entries are automatically skipped
- **Cache cleanup**: Expired entries are cleared on server startup
- **Manual refresh**: Use `refresh_cache()` to force update

## Database Schema

The `b3_stock_cache` table stores:

- `ticker` (TEXT PRIMARY KEY) - Stock ticker code
- `data` (JSONB) - Complete snapshot data
- `created_at` (TIMESTAMP) - Creation timestamp
- `updated_at` (TIMESTAMP) - Last update timestamp
- `expires_at` (TIMESTAMP) - Expiration timestamp

## Integration with Damodaran MCP

This server is designed to work alongside the Damodaran MCP server:

1. **Fundamentus MCP** provides current fundamental data (D/E Ratio, ICR, etc.)
2. **Damodaran MCP** uses this data to calculate levered beta and synthetic ratings

**Example workflow:**
```python
# Get D/E ratio from Fundamentus
metrics = get_fundamental_metrics("PETR4")
de_ratio = metrics["debt_to_equity"]

# Calculate levered beta using Damodaran MCP
beta = calculate_levered_beta("Oil & Gas", de_ratio)
```

## Error Handling

All tools return structured error responses:

```json
{
  "error": "Error message",
  "ticker": "PETR4"
}
```

Common errors:
- Ticker not found
- Fundamentus scraping failure
- Database connection issues
- Invalid ticker format

## Development

### Local Development (without Docker)

1. Install dependencies:
```bash
cd /home/ds/projects/ai_utils/mcp/fundamentus_b3
uv sync
```

2. Set up PostgreSQL (or use existing instance)

3. Run the server:
```bash
python -m fundamentus_b3.server
```

### Testing

Test individual tools using the MCP client or directly:

```python
from fundamentus_b3.server import get_b3_snapshot

result = get_b3_snapshot("PETR4")
print(result)
```

## Notes

- The `fundamentus` library uses web scraping, which may be fragile to website changes
- Rate limiting: Consider adding delays between Fundamentus calls to avoid overloading
- Future enhancement: Implement fallback to Brapi/FMP APIs when Fundamentus fails
- Ticker normalization: All tickers are normalized (uppercase, `.SA` suffix removed)

## License

This project is for internal/educational use. Ensure compliance with Fundamentus.com.br terms of service.

