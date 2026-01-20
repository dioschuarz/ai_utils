# Web Summarizer MCP Server

FastMCP server for summarizing web content using Crawl4AI and Google Gemini.

## Overview

This MCP server provides intelligent web content summarization by:
- Crawling web pages using Crawl4AI (with Playwright)
- Extracting clean, LLM-ready content
- Generating concise summaries using Google Gemini 2.0 Flash
- Managing rate limits automatically (4000 req/min, 4M tokens/min)
- Processing multiple URLs in parallel

## Services

- MCP server (SSE): `http://localhost:8103/sse`

## Environment

Create a `.env` file in this folder with:

```env
# MCP Server Configuration
MCP_HOST=0.0.0.0
MCP_PORT=8000

# Gemini API Configuration (REQUIRED)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash-exp

# Rate Limiting Configuration
MAX_TOKENS_PER_MINUTE=4000000
MAX_REQUESTS_PER_MINUTE=4000
MAX_CONCURRENT_REQUESTS=5

# Request Limits
MAX_URLS_PER_REQUEST=10

# Crawler Configuration
CRAWL_TIMEOUT_SECONDS=30
CRAWL_MAX_RETRIES=2
```

### Required Configuration

- **GEMINI_API_KEY**: Your Google Gemini API key (required)
  - Get one at: https://aistudio.google.com/app/apikey

### Optional Configuration

- **GEMINI_MODEL**: Gemini model to use (default: `gemini-2.0-flash-exp`)
- **MAX_TOKENS_PER_MINUTE**: Token rate limit (default: 4000000)
- **MAX_REQUESTS_PER_MINUTE**: Request rate limit (default: 4000)
- **MAX_CONCURRENT_REQUESTS**: Concurrent processing limit (default: 5)
- **MAX_URLS_PER_REQUEST**: Maximum URLs per request (default: 10)
- **CRAWL_TIMEOUT_SECONDS**: Timeout per URL crawl (default: 30)
- **CRAWL_MAX_RETRIES**: Retry attempts for failed crawls (default: 2)

## Build and Run (Docker)

1. Ensure the external network exists:

```bash
docker network create investment-net
```

2. Start services:

```bash
docker compose -f /home/ds/projects/ai_utils/mcp/web_summarizer_mcp/docker-compose.yml up --build
```

Or use the unified docker-compose from the parent directory:

```bash
docker compose -f /home/ds/projects/ai_utils/mcp/docker-compose.yml up -d web-summarizer-mcp
```

## Tools

The server exposes 1 MCP tool:

### `summarize_web(urls: list[str], titles: Optional[list[str]] = None, max_urls: int = 10, timeout_per_url: int = 30)`

Summarize web content from URLs using Crawl4AI and Gemini.

**Parameters:**
- `urls`: List of URLs to summarize (required, max 10)
- `titles`: Optional list of titles corresponding to URLs (helps with summarization)
- `max_urls`: Maximum number of URLs to process (default: 10, max: 10)
- `timeout_per_url`: Timeout in seconds for each URL crawl (default: 30, range: 10-120)

**Returns JSON with:**
- `summaries`: Array of summary results (one per URL)
  - `url`: Original URL
  - `title`: Article title (if provided)
  - `summary`: Generated summary text
  - `status`: "success", "failed", or "partial"
  - `tokens_used`: Tokens consumed for this summary
  - `processing_time_seconds`: Time taken to process this URL
  - `error`: Error message (if failed)
  - `error_code`: Error code (if failed)
- `metadata`: Processing statistics
  - `total_requested`: Number of URLs requested
  - `total_processed`: Number of URLs processed
  - `total_succeeded`: Number of successful summaries
  - `total_failed`: Number of failed summaries
  - `total_partial`: Number of partial summaries (crawl succeeded, summarization failed)
  - `total_tokens_used`: Total tokens consumed
  - `total_processing_time_seconds`: Total processing time
- `errors`: Array of error details for failed URLs (if any)
- `rate_limit_stats`: Current rate limiter statistics

## Examples

### Basic Usage

```python
result = await session.call_tool(
    "summarize_web",
    arguments={
        "urls": [
            "https://example.com/article1",
            "https://example.com/article2"
        ]
    }
)
```

### With Titles

```python
result = await session.call_tool(
    "summarize_web",
    arguments={
        "urls": [
            "https://example.com/article1",
            "https://example.com/article2"
        ],
        "titles": [
            "Article 1 Title",
            "Article 2 Title"
        ]
    }
)
```

### Integration with yfinance_mcp

```python
# Step 1: Get news URLs from Yahoo Finance
news_result = await session.call_tool(
    "yfinance_get_ticker_news",
    arguments={"symbol": "AAPL"}
)

# Parse news data to extract URLs
news_data = json.loads(news_result)
urls = [item["canonicalUrl"]["url"] for item in news_data if "canonicalUrl" in item]

# Step 2: Summarize the news articles
summary_result = await session.call_tool(
    "summarize_web",
    arguments={
        "urls": urls[:10],  # Limit to 10 URLs
        "max_urls": 10
    }
)
```

## Rate Limiting

The server automatically manages rate limits:

- **Token Tracking**: Sliding window of 60 seconds tracks token usage
- **Request Tracking**: Sliding window of 60 seconds tracks request count
- **Automatic Waiting**: If limits are approached, the server waits before processing
- **Safety Margin**: Uses 90% of configured limits to avoid exceeding quotas
- **Concurrent Limiting**: Semaphore limits concurrent requests (default: 5)

### Rate Limit Statistics

Each response includes `rate_limit_stats`:

```json
{
  "rate_limit_stats": {
    "tokens_used": 12345,
    "tokens_limit": 3600000,
    "tokens_percent": 0.34,
    "requests_used": 15,
    "requests_limit": 3600,
    "requests_percent": 0.42
  }
}
```

## Error Handling

The server handles errors gracefully:

- **Partial Failures**: If one URL fails, others continue processing
- **Retry Logic**: Automatic retries for transient errors (network, timeouts)
- **Fallback Content**: If summarization fails, returns crawled content as fallback
- **Error Codes**: Structured error codes for programmatic handling

### Error Codes

- `INVALID_URL`: URL is malformed or invalid
- `CRAWL_TIMEOUT`: Timeout while crawling URL
- `CRAWL_ERROR`: Generic crawling error
- `RATE_LIMIT_EXCEEDED`: Rate limit exceeded
- `GEMINI_ERROR`: Error from Gemini API
- `TOKEN_LIMIT_EXCEEDED`: Content too large for model
- `NETWORK_ERROR`: Network connectivity error
- `UNKNOWN_ERROR`: Unexpected error

## Performance Considerations

### Processing Time

- **Per URL**: Typically 5-15 seconds (crawl + summarize)
- **Parallel Processing**: Up to 5 URLs processed simultaneously
- **Total Time**: For 10 URLs, expect 30-60 seconds total

### Token Usage

- **Per Summary**: Typically 1000-3000 tokens (depends on content length)
- **10 URLs**: Expect 10,000-30,000 tokens total
- **Rate Limits**: Configured for 4M tokens/minute (plenty of headroom)

### Best Practices

1. **Batch Processing**: Process multiple URLs in one request (up to 10)
2. **Provide Titles**: Include titles when available (improves summarization quality)
3. **Monitor Rate Limits**: Check `rate_limit_stats` in responses
4. **Handle Errors**: Check `status` field and handle failures appropriately
5. **Timeout Settings**: Adjust `timeout_per_url` based on site complexity

## Troubleshooting

### "GEMINI_API_KEY environment variable is required"

- Ensure `.env` file exists in the `web_summarizer_mcp` directory
- Verify `GEMINI_API_KEY` is set correctly
- Check that the Docker container has access to the `.env` file

### Rate Limit Errors

- Check your Gemini API quota limits
- Reduce `MAX_URLS_PER_REQUEST` or `MAX_CONCURRENT_REQUESTS`
- Monitor `rate_limit_stats` in responses
- Wait before making additional requests

### Crawl Timeouts

- Increase `CRAWL_TIMEOUT_SECONDS` (default: 30)
- Some sites may be slow to load
- Check if URLs are accessible

### Empty or Short Summaries

- Verify URLs are accessible and contain meaningful content
- Some sites may block automated crawlers
- Check error messages in response for details

## Architecture

```
Client → summarize_web tool
  ↓
For each URL (parallel, max 5 concurrent):
  1. Crawl URL (Crawl4AI + Playwright)
  2. Extract clean markdown content
  3. Check rate limits (tokens/requests)
  4. Summarize with Gemini
  5. Record usage
  ↓
Return aggregated results
```

## Dependencies

- **Crawl4AI**: Web crawling and content extraction
- **Playwright**: Browser automation (Chromium)
- **Google Generative AI**: Gemini API client
- **FastMCP**: MCP server framework

## Notes

- **No Cache**: Content is always fetched fresh (no caching)
- **Isolated Service**: Runs independently from other MCP servers
- **Reusable**: Can be used with any source of URLs, not just Yahoo Finance
- **Resource Intensive**: Requires significant memory for Playwright browser instances
