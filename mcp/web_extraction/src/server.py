import asyncio
import logging
import random
import time
import json
from typing import Annotated, Optional, List, Dict, Tuple

import httpx
import trafilatura
from fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from .config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_settings = get_settings()
mcp = FastMCP("web-extraction-mcp")

# 24-hour cache TTL
CACHE_TTL = 86400
# Cache format: { url: (timestamp, payload_dict) }
_cache: Dict[str, Tuple[float, dict]] = {}

# Semaphore for concurrent crawls
_crawl_semaphore = asyncio.Semaphore(_settings.max_concurrent_crawls)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
]


class ExtractedArticlePayload(BaseModel):
    """Represents scraped and cleaned article body content."""
    cleaned_markdown: str = Field(..., description="Cleaned, token-efficient body in markdown")
    extracted_title: str = Field(..., description="Title extracted from page content")
    canonical_url: str = Field(..., description="Canonical URL of the source article")
    author: Optional[str] = Field(default=None, description="Article author")
    published_date: Optional[str] = Field(default=None, description="Published date string")


async def _extract_single_url(url: str, timeout: int, max_retries: int = 2) -> dict:
    """Crawl and extract a single URL with retries."""
    # Check cache first
    if url in _cache:
        timestamp, cached_payload = _cache[url]
        if time.time() - timestamp < CACHE_TTL:
            logger.info(f"Cache hit for URL: {url}")
            return cached_payload

    logger.info(f"Extracting content from URL: {url}")
    cleaned_markdown = ""
    extracted_title = "Untitled Article"
    author = None
    published_date = None

    for attempt in range(max_retries + 1):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com/",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        try:
            async with _crawl_semaphore:
                async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=timeout) as client:
                    response = await client.get(url)
                    
                    if response.status_code == 200:
                        content = trafilatura.extract(
                            response.text,
                            include_comments=False,
                            include_tables=True,
                            output_format="markdown"
                        )
                        
                        metadata = trafilatura.extract_metadata(response.text)
                        if metadata:
                            extracted_title = metadata.title or extracted_title
                            author = metadata.author
                            published_date = metadata.date

                        if content and len(content) > 150:
                            cleaned_markdown = content
                            logger.info(f"Successfully extracted {len(content)} chars from {url}")
                            break
                        else:
                            logger.warning(f"Content too short or empty for {url}")
                    elif response.status_code in [429, 403]:
                        wait_time = (2 ** attempt) + random.uniform(1, 3)
                        logger.warning(f"Rate limited ({response.status_code}) for {url}. Waiting {wait_time:.1f}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.warning(f"HTTP {response.status_code} for {url}")
                        
        except Exception as e:
            logger.error(f"Error crawling {url} (attempt {attempt+1}/{max_retries+1}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(2)
                continue

    if not cleaned_markdown:
        logger.warning(f"Extraction failed completely for {url}. Returning fallback.")
        cleaned_markdown = f"Failed to retrieve content for URL: {url}"

    payload_dict = {
        "cleaned_markdown": cleaned_markdown,
        "extracted_title": extracted_title,
        "canonical_url": url,
        "author": author,
        "published_date": published_date,
    }

    # Save to cache
    _cache[url] = (time.time(), payload_dict)
    return payload_dict


@mcp.tool(
    name="extract_content",
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def extract_content(
    urls: Annotated[List[str], Field(description="List of URLs to crawl and convert to markdown")],
    timeout: Annotated[int, Field(description="Timeout in seconds per URL extraction")] = 30,
) -> str:
    """Crawl multiple URLs concurrently and extract clean, token-efficient markdown content from each."""
    if not urls:
        return json.dumps({"results": []})

    tasks = [
        _extract_single_url(url, timeout)
        for url in urls
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    extracted_pages = []
    for url, res in zip(urls, results):
        if isinstance(res, Exception):
            logger.error(f"Failed to crawl {url}: {res}")
            extracted_pages.append({
                "cleaned_markdown": f"Error crawling URL: {url} - {str(res)}",
                "extracted_title": "Failed to Crawl",
                "canonical_url": url,
                "author": None,
                "published_date": None,
            })
        else:
            extracted_pages.append(res)

    return json.dumps({"results": extracted_pages})


from starlette.responses import JSONResponse

@mcp.custom_route("/health", methods=["GET"])
async def health(request):
    """Health check endpoint."""
    return JSONResponse({"status": "healthy"})


def main() -> None:
    logger.info(f"Starting Web Content Extraction MCP on {_settings.mcp_host}:{_settings.mcp_port}")
    mcp.run(
        transport="http",
        host=_settings.mcp_host,
        port=_settings.mcp_port,
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
