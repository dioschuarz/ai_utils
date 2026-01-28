"""FastMCP server exposing web summarization tools."""

import asyncio
import logging
import time
from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .config import Settings, get_settings
from .crawler import crawl_url
from .rate_limiter import TokenRateLimiter
from .summarizer import Summarizer
from .utils import dump_json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_settings = get_settings()
mcp = FastMCP(
    "web-summarizer-mcp",
    host=_settings.mcp_host,
    port=_settings.mcp_port,
)

# Initialize rate limiter and summarizer
_rate_limiter = TokenRateLimiter(
    max_tokens_per_minute=_settings.max_tokens_per_minute,
    max_requests_per_minute=_settings.max_requests_per_minute,
    max_concurrent_requests=_settings.max_concurrent_requests,
)

_summarizer = Summarizer(_settings, _rate_limiter)

# Semaphore for concurrent crawling (browser is resource intensive)
# We use the same limit as max_concurrent_requests, or could be separate.
_crawl_semaphore = asyncio.Semaphore(_settings.max_concurrent_requests)


@mcp.tool(
    name="summarize_web",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def summarize_web(
    urls: Annotated[
        list[str],
        Field(
            description=(
                "List of URLs to summarize. Each URL will be crawled and summarized. "
                "Maximum 10 URLs per request."
            )
        ),
    ],
    titles: Annotated[
        Optional[list[str]],
        Field(
            description=(
                "Optional list of titles corresponding to URLs. "
                "If provided, must match the length of urls list."
            ),
        ),
    ] = None,
    max_urls: Annotated[
        int,
        Field(
            description="Maximum number of URLs to process (default: 10, max: 10)",
            ge=1,
            le=10,
        ),
    ] = 10,
    timeout_per_url: Annotated[
        int,
        Field(
            description="Timeout in seconds for each URL crawl (default: 30)",
            ge=10,
            le=120,
        ),
    ] = 30,
) -> str:
    """Summarize web content from URLs using Crawl4AI and Gemini.

    This tool crawls each URL, extracts clean content, and generates a concise
    summary using Google Gemini. It handles rate limiting automatically and
    processes URLs in parallel for efficiency.

    Returns JSON with:
    - summaries: Array of summary results (one per URL)
    - metadata: Processing statistics (total requested, succeeded, failed, etc.)
    - errors: Array of error details for failed URLs

    Each summary includes:
    - url: Original URL
    - title: Article title (if provided)
    - summary: Generated summary text
    - status: "success" or "failed"
    - tokens_used: Tokens consumed for this summary
    - processing_time_seconds: Time taken to process this URL
    """
    start_time = time.time()

    # Validate inputs
    if not urls:
        return dump_json(
            {
                "error": "At least one URL is required",
                "error_code": "INVALID_INPUT",
            }
        )

    # Limit number of URLs
    urls_to_process = urls[:max_urls]
    if len(urls) > max_urls:
        logger.warning(
            f"Limiting URLs from {len(urls)} to {max_urls} (max_urls parameter)"
        )

    # Validate titles if provided
    if titles is not None:
        if len(titles) != len(urls_to_process):
            return dump_json(
                {
                    "error": (
                        f"titles list length ({len(titles) if titles else 0}) "
                        f"must match urls list length ({len(urls_to_process)})"
                    ),
                    "error_code": "INVALID_INPUT",
                }
            )
        # Limit titles to match URLs
        titles = titles[:max_urls]
    else:
        # Create empty titles list
        titles = [None] * len(urls_to_process)

    logger.info(
        f"Processing {len(urls_to_process)} URLs with timeout={timeout_per_url}s"
    )

    # Process URLs in parallel
    async def process_single_url(url: str, title: Optional[str], index: int) -> dict:
        """Process a single URL: crawl + summarize."""
        url_start_time = time.time()

        try:
            # Step 1: Crawl URL (with semaphore to limit concurrent browser instances)
            async with _crawl_semaphore:
                crawl_result = await crawl_url(
                    url=url,
                    timeout=timeout_per_url,
                    max_retries=_settings.crawl_max_retries,
                )

            if not crawl_result["success"]:
                return {
                    "url": url,
                    "title": title,
                    "summary": "",
                    "status": "failed",
                    "tokens_used": 0,
                    "processing_time_seconds": time.time() - url_start_time,
                    "error": crawl_result["error"],
                    "error_code": crawl_result["error_code"],
                }

            # Step 2: Summarize content
            summary_result = await _summarizer.summarize_article(
                content=crawl_result["content"],
                url=url,
                title=title or "Article",
            )

            processing_time = time.time() - url_start_time

            if summary_result["success"]:
                return {
                    "url": url,
                    "title": title,
                    "summary": summary_result["summary"],
                    "status": "success",
                    "tokens_used": summary_result["tokens_used"],
                    "processing_time_seconds": processing_time,
                    "error": None,
                    "error_code": None,
                }
            else:
                # Summarization failed, but we have the crawled content
                # Return partial result with crawled content as fallback
                return {
                    "url": url,
                    "title": title,
                    "summary": crawl_result["content"][:1000]
                    + "...",  # Truncated content as fallback
                    "status": "partial",
                    "tokens_used": 0,
                    "processing_time_seconds": processing_time,
                    "error": summary_result["error"],
                    "error_code": summary_result["error_code"],
                    "note": "Summarization failed, returning crawled content",
                }

        except Exception as e:
            logger.error(f"Unexpected error processing {url}: {e}", exc_info=True)
            return {
                "url": url,
                "title": title,
                "summary": "",
                "status": "failed",
                "tokens_used": 0,
                "processing_time_seconds": time.time() - url_start_time,
                "error": f"Unexpected error: {str(e)}",
                "error_code": "UNKNOWN_ERROR",
            }

    # Process all URLs concurrently (with semaphore limiting)
    tasks = [
        process_single_url(url, title, idx)
        for idx, (url, title) in enumerate(zip(urls_to_process, titles))
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results and collect errors
    summaries = []
    errors = []
    total_tokens = 0

    for result in results:
        if isinstance(result, Exception):
            logger.error(f"Task raised exception: {result}", exc_info=True)
            errors.append(
                {
                    "url": "unknown",
                    "error": str(result),
                    "error_code": "UNKNOWN_ERROR",
                }
            )
        else:
            summaries.append(result)
            if result["tokens_used"]:
                total_tokens += result["tokens_used"]
            if result["status"] == "failed" or result.get("error"):
                errors.append(
                    {
                        "url": result["url"],
                        "error": result.get("error", "Unknown error"),
                        "error_code": result.get("error_code", "UNKNOWN_ERROR"),
                    }
                )

    # Calculate statistics
    total_processing_time = time.time() - start_time
    total_succeeded = sum(1 for s in summaries if s["status"] == "success")
    total_failed = sum(1 for s in summaries if s["status"] == "failed")
    total_partial = sum(1 for s in summaries if s["status"] == "partial")

    response = {
        "summaries": summaries,
        "metadata": {
            "total_requested": len(urls_to_process),
            "total_processed": len(summaries),
            "total_succeeded": total_succeeded,
            "total_failed": total_failed,
            "total_partial": total_partial,
            "total_tokens_used": total_tokens,
            "total_processing_time_seconds": round(total_processing_time, 2),
        },
    }

    if errors:
        response["errors"] = errors

    # Add rate limiter stats
    response["rate_limit_stats"] = _rate_limiter.get_current_stats()

    return dump_json(response)


def main() -> None:
    """Run the MCP server."""
    logger.info(f"Starting Web Summarizer MCP on {_settings.mcp_host}:{_settings.mcp_port}")
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
