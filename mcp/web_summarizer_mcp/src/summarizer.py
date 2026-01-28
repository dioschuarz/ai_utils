"""Gemini-based summarization for web content."""

import logging
import pathlib
from typing import Optional

from google import genai

from .config import Settings
from .rate_limiter import TokenRateLimiter
from .utils import estimate_tokens

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
    """Handles summarization using Google Gemini API."""

    def __init__(self, settings: Settings, rate_limiter: TokenRateLimiter):
        """Initialize summarizer.

        Args:
            settings: Application settings
            rate_limiter: Rate limiter instance
        """
        self.settings = settings
        self.rate_limiter = rate_limiter

        # Initialize Gemini API client
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model_name = settings.gemini_model

    def close(self) -> None:
        """Close the Gemini API client and release resources."""
        if hasattr(self, "client") and self.client:
            self.client.close()

    def __del__(self) -> None:
        """Cleanup client on object destruction."""
        try:
            self.close()
        except Exception:
            # Ignore errors during cleanup
            pass

    async def summarize_article(
        self,
        content: str,
        url: str,
        title: Optional[str] = None,
    ) -> dict:
        """Summarize an article using Gemini.

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
        max_retries = 10  # Increased from 3 to 10 for "guaranteed" execution
        last_error = None
        last_error_code = None

        for attempt in range(max_retries + 1):
            try:
                # Check rate limits and wait if needed
                await self.rate_limiter.wait_if_needed(estimated_tokens)

                # Acquire semaphore for concurrent request limiting
                await self.rate_limiter.acquire()

                try:
                    logger.info(f"Summarizing article from {url} (est. {estimated_tokens} tokens)")

                    # Generate summary using async client
                    response = await self.client.aio.models.generate_content(
                        model=self.model_name,
                        contents=prompt,
                    )

                    # Extract summary text
                    # Try using .text property first (works for simple text responses)
                    try:
                        summary = response.text.strip()
                    except (ValueError, AttributeError):
                        # Fallback: extract text from candidates manually
                        if (
                            response.candidates
                            and response.candidates[0].content
                            and response.candidates[0].content.parts
                        ):
                            text_parts = [
                                part.text
                                for part in response.candidates[0].content.parts
                                if hasattr(part, "text") and part.text
                            ]
                            summary = " ".join(text_parts).strip() if text_parts else ""
                        else:
                            summary = ""

                    if summary:
                        # Extract token usage
                        tokens_used = (
                            response.usage_metadata.total_token_count
                            if hasattr(response, "usage_metadata")
                            and response.usage_metadata
                            and hasattr(response.usage_metadata, "total_token_count")
                            else estimated_tokens
                        )

                        # Record usage
                        await self.rate_limiter.record_request(tokens_used)

                        logger.info(
                            f"Successfully summarized {url}: {len(summary)} chars, "
                            f"{tokens_used} tokens"
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
                        error_msg = "Empty response from Gemini"
                        logger.warning(f"{error_msg} for {url}")
                        return {
                            "success": False,
                            "summary": "",
                            "tokens_used": 0,
                            "error": error_msg,
                            "error_code": "GEMINI_ERROR",
                        }

                finally:
                    self.rate_limiter.release()

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error summarizing {url} (attempt {attempt+1}/{max_retries+1}): {error_msg}")
                last_error = error_msg
                
                # Check for specific error types
                if "429" in error_msg or "quota" in error_msg.lower() or "resourceexhausted" in error_msg.lower():
                    last_error_code = "RATE_LIMIT_EXCEEDED"
                    if attempt < max_retries:
                        # Exponential backoff with jitter/cap: 5, 10, 20, 30, 30, ...
                        wait_time = min(5 * (2 ** attempt), 60)
                        logger.warning(f"Rate limit hit. Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                        continue
                elif "token" in error_msg.lower() or "length" in error_msg.lower():
                    last_error_code = "TOKEN_LIMIT_EXCEEDED"
                    # Don't retry token limit errors
                    break
                else:
                    last_error_code = "GEMINI_ERROR"
                    # Retry generic errors just in case
                    if attempt < max_retries:
                        wait_time = 2 ** attempt
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
            "error_code": last_error_code or "GEMINI_ERROR",
        }
