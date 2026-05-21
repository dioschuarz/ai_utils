"""OpenRouter-based summarization for web content."""

import logging
import pathlib
from typing import Optional

from .config import Settings
from .rate_limiter import TokenRateLimiter
from .utils import estimate_tokens
from .llm_transport import LLMTransport

logger = logging.getLogger(__name__)


def _load_prompt_template() -> str:
    """Load prompt template from prompts/summarization_prompt.txt.

    Returns:
        Prompt template string with placeholders {title}, {url}, {content}

    Raises:
        FileNotFoundError: If prompt template file is not found
    """
    prompt_path = pathlib.Path(__file__).parent.parent / "prompts" / "summarization_prompt.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


# Load prompt template once at module level
SUMMARIZATION_PROMPT = _load_prompt_template()


class Summarizer:
    """Handles summarization using LLMTransport."""

    def __init__(self, settings: Settings, rate_limiter: TokenRateLimiter):
        """Initialize summarizer.

        Args:
            settings: Application settings
            rate_limiter: Rate limiter instance
        """
        self.settings = settings
        self.rate_limiter = rate_limiter

        # Global Request Limiter to respect maximum allowed rpm bounds securely
        try:
            from aiolimiter import AsyncLimiter
            self.request_limiter = AsyncLimiter(max_rate=max(1, settings.max_requests_per_minute), time_period=60)
        except ImportError:
            self.request_limiter = None

        # Initialize LLM Transport
        self.transport = LLMTransport()
        self.provider = "cerebras"

    async def close(self) -> None:
        """Close the API client and release resources."""
        pass

    def __del__(self) -> None:
        """Cleanup client on object destruction."""
        pass

    async def summarize_article(
        self,
        content: str,
        url: str,
        title: Optional[str] = None,
    ) -> dict:
        """Summarize an article using LLMTransport.

        Args:
            content: Article content (markdown)
            url: Article URL
            title: Optional article title

        Returns:
            Dictionary with:
                - success: bool
                - summary: str (summary if successful)
                - tokens_used: int (tokens used)
                - error: str (error message if failed)
                - error_code: str (error code if failed)
        """
        if not content or len(content.strip()) < 50:
            return {
                "success": False,
                "summary": "",
                "tokens_used": 0,
                "error": "Content too short or empty",
                "error_code": "TOKEN_LIMIT_EXCEEDED",
            }

        # Prepare prompt
        article_title = title or "Article"
        prompt = SUMMARIZATION_PROMPT.format(
            title=article_title,
            url=url,
            content=content[:50000],  # Limit content to avoid token limits
        )

        # Estimate tokens (prompt + response)
        estimated_tokens = estimate_tokens(prompt) + 500  # Add margin for response

        # Retry loop for API errors
        max_retries = 10  # Increased for "guaranteed" execution
        last_error = None
        last_error_code = None

        for attempt in range(max_retries + 1):
            try:
                # Check rate limits and wait if needed
                await self.rate_limiter.wait_if_needed(estimated_tokens)

                # Limit absolute RPS bounds prior to concurrent burst lock
                if hasattr(self, 'request_limiter') and self.request_limiter:
                    await self.request_limiter.acquire()

                # Acquire semaphore for concurrent request limiting
                await self.rate_limiter.acquire()

                try:
                    logger.info(f"Summarizing article from {url} (est. {estimated_tokens} tokens) via {self.provider}")

                    # Generate summary using LLMTransport
                    summary = await self.transport.call(
                        prompt=prompt,
                        provider=self.provider,
                        max_tokens=2000,
                        temperature=0.3
                    )

                    if summary:
                        # Extract token usage (estimate since call returns string)
                        tokens_used = estimated_tokens

                        # Record usage
                        await self.rate_limiter.record_request(tokens_used)

                        logger.info(
                            f"Successfully summarized {url}: {len(summary)} chars, "
                            f"{tokens_used} tokens (estimated)"
                        )

                        return {
                            "success": True,
                            "summary": summary,
                            "tokens_used": tokens_used,
                            "error": None,
                            "error_code": None,
                        }
                    else:
                        # Empty response is not a rate limit error, don't retry in this loop
                        error_msg = "Empty response from LLMTransport"
                        logger.warning(f"{error_msg} for {url}")
                        return {
                            "success": False,
                            "summary": "",
                            "tokens_used": 0,
                            "error": error_msg,
                            "error_code": "LLM_ERROR",
                        }

                finally:
                    self.rate_limiter.release()

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error summarizing {url} (attempt {attempt+1}/{max_retries+1}): {error_msg}")
                last_error = error_msg
                
                # Check for specific error types
                if any(x in error_msg.lower() for x in ["429", "rate limit", "quota", "exhausted", "503", "unavailable"]):
                    last_error_code = "RATE_LIMIT_EXCEEDED"
                    if attempt < max_retries:
                        # Exponential backoff with jitter/cap: 5, 10, 20, 30, 30, ...
                        wait_time = min(5 * (2 ** attempt), 60)
                        logger.warning(f"Rate limit hit. Waiting {wait_time}s before retry...")
                        import asyncio
                        await asyncio.sleep(wait_time)
                        continue
                elif any(x in error_msg.lower() for x in ["token", "length", "context_length"]):
                    last_error_code = "TOKEN_LIMIT_EXCEEDED"
                    # Don't retry token limit errors
                    break
                else:
                    last_error_code = "LLM_ERROR"
                    # Retry generic errors just in case
                    if attempt < max_retries:
                        wait_time = 2 ** attempt
                        import asyncio
                        await asyncio.sleep(wait_time)
                        continue

        # If we get here, all retries failed
        # Return partial success with raw content to satisfy "guaranteed output" requirement
        logger.error(f"All summarization retries failed for {url}. Returning raw content.")
        return {
            "success": False, # Technically failed summarization
            "summary": f"FAILED TO SUMMARIZE due to API limits. Here is the raw content start: {content[:500]}...",
            "tokens_used": 0,
            "error": last_error,
            "error_code": last_error_code or "LLM_ERROR",
        }
