"""Lightweight crawler with aggressive retries and backoff for news extraction."""

import asyncio
import logging
import httpx
import trafilatura
import random
import time

logger = logging.getLogger(__name__)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
]

async def crawl_url(url: str, timeout: int = 20, max_retries: int = 3) -> dict:
    """Crawl a URL using Trafilatura with exponential backoff on 429/403."""
    
    for attempt in range(max_retries + 1):
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        try:
            logger.info(f"Crawling {url} (Attempt {attempt+1}/{max_retries+1})")
            async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=timeout) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    content = trafilatura.extract(response.text, include_comments=False, include_tables=True)
                    if content and len(content) > 150:
                        logger.info(f"Successfully extracted {len(content)} chars from {url}")
                        return {"success": True, "content": content, "error": None, "error_code": None}
                    else:
                        logger.warning(f"Extraction returned empty or too short content for {url}")
                
                elif response.status_code in [429, 403]:
                    # Rate limited or Forbidden - Wait and retry with backoff
                    wait_time = (2 ** attempt) + random.uniform(1, 3)
                    logger.warning(f"Status {response.status_code} for {url}. Waiting {wait_time:.1f}s before retry...")
                    await asyncio.sleep(wait_time)
                    continue
                
                else:
                    logger.warning(f"HTTP {response.status_code} for {url}")

        except Exception as e:
            logger.error(f"Exception during crawl of {url}: {e}")
            if attempt < max_retries:
                await asyncio.sleep(2)
                continue
            return {"success": False, "content": "", "error": str(e), "error_code": "CRAWL_FAILED"}

    return {"success": False, "content": "", "error": "Failed after multiple retries", "error_code": "MAX_RETRIES_EXCEEDED"}
