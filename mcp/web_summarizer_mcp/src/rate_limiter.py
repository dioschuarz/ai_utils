"""Rate limiter for Gemini API with token and request tracking."""

import asyncio
import logging
import time
from collections import deque
from typing import Deque

logger = logging.getLogger(__name__)


class TokenRateLimiter:
    """Rate limiter that tracks tokens and requests per minute using sliding window."""

    def __init__(
        self,
        max_tokens_per_minute: int,
        max_requests_per_minute: int,
        max_concurrent_requests: int = 5,
        safety_margin: float = 0.9,
    ):
        """Initialize rate limiter.

        Args:
            max_tokens_per_minute: Maximum tokens allowed per minute
            max_requests_per_minute: Maximum requests allowed per minute
            max_concurrent_requests: Maximum concurrent requests (semaphore limit)
            safety_margin: Safety margin to use (e.g., 0.9 = 90% of limit)
        """
        self.max_tokens = int(max_tokens_per_minute * safety_margin)
        self.max_requests = int(max_requests_per_minute * safety_margin)
        self.max_concurrent = max_concurrent_requests

        # Sliding window: deque of (timestamp, tokens_used) tuples
        self.token_history: Deque[tuple[float, int]] = deque()
        self.request_history: Deque[float] = deque()

        # Semaphore for concurrent request limiting
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)

        # Lock for thread-safe operations
        self.lock = asyncio.Lock()

        # Window size in seconds (1 minute)
        self.window_seconds = 60.0

    def _clean_old_entries(self, current_time: float) -> None:
        """Remove entries older than the window from history."""
        cutoff_time = current_time - self.window_seconds

        # Clean token history
        while self.token_history and self.token_history[0][0] < cutoff_time:
            self.token_history.popleft()

        # Clean request history
        while self.request_history and self.request_history[0] < cutoff_time:
            self.request_history.popleft()

    def _get_current_usage(self, current_time: float) -> tuple[int, int]:
        """Get current token and request usage in the window.

        Returns:
            Tuple of (current_tokens, current_requests)
        """
        self._clean_old_entries(current_time)

        current_tokens = sum(tokens for _, tokens in self.token_history)
        current_requests = len(self.request_history)

        return current_tokens, current_requests

    async def wait_if_needed(self, estimated_tokens: int) -> None:
        """Wait if needed to avoid exceeding rate limits.

        Args:
            estimated_tokens: Estimated tokens for the upcoming request

        Raises:
            RuntimeError: If estimated tokens would exceed limit even after waiting
        """
        async with self.lock:
            current_time = time.time()
            current_tokens, current_requests = self._get_current_usage(current_time)

            # Check if we can accommodate this request
            if current_tokens + estimated_tokens > self.max_tokens:
                # Calculate how long to wait
                if self.token_history:
                    oldest_time = self.token_history[0][0]
                    wait_time = (oldest_time + self.window_seconds) - current_time + 1.0
                    if wait_time > 0:
                        logger.warning(
                            f"Token limit approaching. Waiting {wait_time:.1f}s. "
                            f"Current: {current_tokens}/{self.max_tokens} tokens"
                        )
                        await asyncio.sleep(wait_time)
                        # Recalculate after waiting
                        current_time = time.time()
                        current_tokens, current_requests = self._get_current_usage(
                            current_time
                        )

            if current_tokens + estimated_tokens > self.max_tokens:
                raise RuntimeError(
                    f"Estimated tokens ({estimated_tokens}) would exceed limit "
                    f"({self.max_tokens}). Current usage: {current_tokens} tokens"
                )

            if current_requests >= self.max_requests:
                # Calculate wait time for requests
                if self.request_history:
                    oldest_time = self.request_history[0]
                    wait_time = (oldest_time + self.window_seconds) - current_time + 1.0
                    if wait_time > 0:
                        logger.warning(
                            f"Request limit approaching. Waiting {wait_time:.1f}s. "
                            f"Current: {current_requests}/{self.max_requests} requests"
                        )
                        await asyncio.sleep(wait_time)

    async def record_request(self, tokens_used: int) -> None:
        """Record a completed request and its token usage.

        Args:
            tokens_used: Number of tokens actually used in the request
        """
        async with self.lock:
            current_time = time.time()
            self.token_history.append((current_time, tokens_used))
            self.request_history.append(current_time)

            # Clean old entries
            self._clean_old_entries(current_time)

    async def acquire(self) -> None:
        """Acquire semaphore for concurrent request limiting."""
        await self.semaphore.acquire()

    def release(self) -> None:
        """Release semaphore after request completes."""
        self.semaphore.release()

    def get_current_stats(self) -> dict:
        """Get current rate limit statistics.

        Returns:
            Dictionary with current usage stats
        """
        current_time = time.time()
        current_tokens, current_requests = self._get_current_usage(current_time)

        return {
            "tokens_used": current_tokens,
            "tokens_limit": self.max_tokens,
            "tokens_percent": (current_tokens / self.max_tokens * 100) if self.max_tokens > 0 else 0,
            "requests_used": current_requests,
            "requests_limit": self.max_requests,
            "requests_percent": (current_requests / self.max_requests * 100) if self.max_requests > 0 else 0,
        }
