"""Crawl4AI wrapper for web content extraction."""

import asyncio
import logging
from typing import Optional

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

logger = logging.getLogger(__name__)

# Global crawler instance (reused across requests)
_crawler: Optional[AsyncWebCrawler] = None
_crawler_lock = asyncio.Lock()


async def get_crawler() -> AsyncWebCrawler:
    """Get or create the global crawler instance.

    Returns:
        AsyncWebCrawler instance
    """
    global _crawler

    async with _crawler_lock:
        if _crawler is None:
            browser_config = BrowserConfig(
                headless=True,
                verbose=False,
            )
            _crawler = AsyncWebCrawler(config=browser_config)
            await _crawler.__aenter__()
            logger.info("Initialized AsyncWebCrawler")

    return _crawler


async def crawl_url(url: str, timeout: int = 30, max_retries: int = 2) -> dict:
    """Crawl a URL and extract clean markdown content.

    Args:
        url: URL to crawl
        timeout: Timeout in seconds
        max_retries: Maximum number of retry attempts

    Returns:
        Dictionary with:
            - success: bool
            - content: str (markdown content if successful)
            - error: str (error message if failed)
            - error_code: ErrorCode (error code if failed)
    """
    if not url or not url.startswith(("http://", "https://")):
        return {
            "success": False,
            "content": "",
            "error": f"Invalid URL: {url}",
            "error_code": "INVALID_URL",
        }

    crawler = await get_crawler()

    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,  # Always fetch fresh content
        word_count_threshold=10,  # Minimum word count to consider valid content
        exclude_external_links=True,  # Don't follow external links
        wait_for_images=False,  # Don't wait for images to load (faster)
    )

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"Crawling {url} (attempt {attempt + 1}/{max_retries + 1})")

            # Use asyncio.wait_for to enforce timeout
            result = await asyncio.wait_for(
                crawler.arun(url=url, config=run_config),
                timeout=timeout,
            )

            if result.success and result.markdown:
                content = result.markdown.strip()
                if len(content) > 100:  # Ensure we got meaningful content
                    logger.info(
                        f"Successfully crawled {url}: {len(content)} characters"
                    )
                    return {
                        "success": True,
                        "content": content,
                        "error": None,
                        "error_code": None,
                    }
                else:
                    logger.warning(
                        f"Content too short for {url}: {len(content)} characters"
                    )
                    return {
                        "success": False,
                        "content": "",
                        "error": f"Content too short or empty: {len(content)} characters",
                        "error_code": "CRAWL_ERROR",
                    }
            else:
                error_msg = result.error_message or "Unknown crawl error"
                logger.warning(f"Crawl failed for {url}: {error_msg}")
                last_error = error_msg

        except asyncio.TimeoutError:
            error_msg = f"Timeout after {timeout}s"
            logger.warning(f"Timeout crawling {url}: {error_msg}")
            last_error = error_msg
            if attempt < max_retries:
                await asyncio.sleep(1)  # Brief pause before retry

        except Exception as e:
            error_msg = f"Error crawling {url}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            last_error = error_msg
            if attempt < max_retries:
                await asyncio.sleep(1)  # Brief pause before retry

    # All retries failed
    return {
        "success": False,
        "content": "",
        "error": last_error or "Unknown error",
        "error_code": "CRAWL_ERROR",
    }


async def cleanup_crawler() -> None:
    """Cleanup the global crawler instance."""
    global _crawler

    async with _crawler_lock:
        if _crawler is not None:
            try:
                await _crawler.__aexit__(None, None, None)
                logger.info("Cleaned up AsyncWebCrawler")
            except Exception as e:
                logger.error(f"Error cleaning up crawler: {e}")
            finally:
                _crawler = None
