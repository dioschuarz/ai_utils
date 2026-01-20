"""Client for calling web_summarizer_mcp from yfinance_mcp."""

import asyncio
import json
import logging
from typing import Optional

from mcp import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)


class WebSummarizerClient:
    """Client for calling web_summarizer_mcp via SSE."""

    def __init__(self, url: str, timeout: int = 60):
        """Initialize client.

        Args:
            url: URL to web_summarizer_mcp SSE endpoint
            timeout: Timeout in seconds for the entire operation
        """
        self.url = url
        self.timeout = timeout

    async def summarize_urls(
        self,
        urls: list[str],
        titles: Optional[list[str]] = None,
        max_urls: int = 10,
        timeout_per_url: int = 30,
    ) -> dict:
        """Summarize URLs using web_summarizer_mcp.

        Args:
            urls: List of URLs to summarize
            titles: Optional list of titles corresponding to URLs
            max_urls: Maximum number of URLs to process
            timeout_per_url: Timeout per URL in seconds

        Returns:
            Dictionary with summary results or error information

        Raises:
            TimeoutError: If operation exceeds timeout
            ConnectionError: If cannot connect to web_summarizer_mcp
        """
        if not urls:
            return {
                "error": "No URLs provided",
                "error_code": "INVALID_INPUT",
            }

        try:
            logger.info(
                f"Connecting to web_summarizer_mcp at {self.url} "
                f"to summarize {len(urls)} URLs"
            )

            # Use asyncio.wait_for to enforce overall timeout
            result = await asyncio.wait_for(
                self._call_summarize_web(urls, titles, max_urls, timeout_per_url),
                timeout=self.timeout,
            )

            return result

        except asyncio.TimeoutError:
            error_msg = f"Timeout after {self.timeout}s while calling web_summarizer_mcp"
            logger.error(error_msg)
            return {
                "error": error_msg,
                "error_code": "WEB_SUMMARIZER_TIMEOUT",
            }

        except Exception as e:
            error_msg = f"Error calling web_summarizer_mcp: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "error": error_msg,
                "error_code": "WEB_SUMMARIZER_ERROR",
            }

    async def _call_summarize_web(
        self,
        urls: list[str],
        titles: Optional[list[str]],
        max_urls: int,
        timeout_per_url: int,
    ) -> dict:
        """Internal method to call summarize_web tool."""
        async with sse_client(url=self.url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Prepare arguments
                arguments = {
                    "urls": urls[:max_urls],
                    "max_urls": max_urls,
                    "timeout_per_url": timeout_per_url,
                }

                if titles:
                    arguments["titles"] = titles[:max_urls]

                # Call the tool
                result = await session.call_tool("summarize_web", arguments=arguments)

                # Extract text from response
                if result.content and len(result.content) > 0:
                    response_text = result.content[0].text
                    try:
                        return json.loads(response_text)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON response: {e}")
                        return {
                            "error": f"Invalid JSON response from web_summarizer_mcp: {str(e)}",
                            "error_code": "INVALID_RESPONSE",
                            "raw_response": response_text[:500],
                        }
                else:
                    return {
                        "error": "Empty response from web_summarizer_mcp",
                        "error_code": "EMPTY_RESPONSE",
                    }
