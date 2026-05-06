"""Figma API Rate Limiter with retry logic and exponential backoff."""
import asyncio
import time
import logging
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)


class FigmaRateLimiter:
    """
    Handles Figma API rate limiting with retry logic, exponential backoff,
    and Retry-After header support.
    """

    def __init__(
        self,
        max_retries: int = 5,
        base_backoff: float = 1.0,
        max_backoff: float = 60.0,
        max_concurrent_requests: int = 10,
    ):
        """
        Initialize rate limiter.

        Args:
            max_retries: Maximum number of retry attempts
            base_backoff: Base delay in seconds for exponential backoff
            max_backoff: Maximum delay in seconds
            max_concurrent_requests: Maximum concurrent requests per minute
        """
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self.max_concurrent_requests = max_concurrent_requests
        self.request_times: list[float] = []
        self._lock = asyncio.Lock()

    async def request_with_retry(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> httpx.Response:
        """
        Make HTTP request with automatic retry on rate limit errors.

        Args:
            client: httpx AsyncClient instance
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            headers: Request headers
            params: Query parameters
            **kwargs: Additional arguments for httpx request

        Returns:
            httpx.Response object

        Raises:
            httpx.HTTPStatusError: If request fails after all retries
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                # Throttle concurrent requests
                await self._throttle_request()

                # Make the request
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    **kwargs,
                )

                # Success - return response
                if response.status_code == 200:
                    return response

                # Handle rate limit (429)
                if response.status_code == 429:
                    retry_after = self._parse_retry_after(response)
                    backoff_time = retry_after or self._calculate_backoff(attempt)

                    if attempt < self.max_retries:
                        logger.warning(
                            f"Figma API rate limit hit (10 req/min). Consider using the Figma Plugin instead, "
                            f"which bypasses API rate limits entirely. "
                            f"Waiting {backoff_time:.0f}s before retry (attempt {attempt + 1}/{self.max_retries + 1})..."
                        )
                        await self._wait_for_rate_limit(backoff_time)
                        continue
                    else:
                        # Max retries reached
                        error_msg = (
                            f"Figma API rate limit hit (10 req/min) after {self.max_retries} retries. "
                            f"Consider using the Figma Plugin instead, which bypasses API rate limits entirely."
                        )
                        logger.error(error_msg)
                        response.raise_for_status()

                # Handle other HTTP errors
                if response.status_code >= 400:
                    logger.error(
                        f"HTTP {response.status_code} error: {response.text[:200]}"
                    )
                    response.raise_for_status()

                return response

            except httpx.HTTPStatusError as e:
                last_exception = e
                if e.response.status_code == 429 and attempt < self.max_retries:
                    retry_after = self._parse_retry_after(e.response)
                    backoff_time = retry_after or self._calculate_backoff(attempt)
                    logger.warning(
                        f"Figma API rate limit hit (10 req/min). Consider using the Figma Plugin instead, "
                        f"which bypasses API rate limits entirely. "
                        f"Waiting {backoff_time:.0f}s before retry (attempt {attempt + 1}/{self.max_retries + 1})..."
                    )
                    await self._wait_for_rate_limit(backoff_time)
                    continue
                raise

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_exception = e
                if attempt < self.max_retries:
                    backoff_time = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Network error on attempt {attempt + 1}: {str(e)}. "
                        f"Retrying in {backoff_time:.2f}s..."
                    )
                    await self._wait_for_rate_limit(backoff_time)
                    continue
                raise

        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        raise RuntimeError("Request failed after all retries without a captured exception")

    def _parse_retry_after(self, response: httpx.Response) -> Optional[float]:
        """
        Parse Retry-After header from response.

        Args:
            response: HTTP response object

        Returns:
            Seconds to wait, or None if header not present
        """
        retry_after = response.headers.get("Retry-After")
        if not retry_after:
            return None

        try:
            # Retry-After can be seconds (integer) or HTTP date
            # Try parsing as integer first
            return float(retry_after)
        except ValueError:
            # Try parsing as HTTP date
            try:
                from email.utils import parsedate_to_datetime
                retry_date = parsedate_to_datetime(retry_after)
                if retry_date:
                    wait_seconds = (retry_date.timestamp() - time.time())
                    return max(0, wait_seconds)
            except Exception:
                pass

        return None

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        backoff = self.base_backoff * (2 ** attempt)
        return min(backoff, self.max_backoff)

    async def _wait_for_rate_limit(self, seconds: float):
        """Wait for specified number of seconds."""
        await asyncio.sleep(seconds)

    def get_rate_limit_status(self) -> dict:
        """Return current rate limiter status.

        Returns:
            dict with requests_in_window, max_requests, remaining,
            and window_resets_in_seconds.
        """
        now = time.time()
        active = [t for t in self.request_times if now - t < 60]
        count = len(active)
        remaining = max(0, self.max_concurrent_requests - count)

        if active:
            oldest = min(active)
            resets_in = max(0, 60 - (now - oldest))
        else:
            resets_in = 0.0

        return {
            "requests_in_window": count,
            "max_requests": self.max_concurrent_requests,
            "remaining": remaining,
            "window_resets_in_seconds": round(resets_in, 1),
        }

    async def _throttle_request(self):
        """
        Throttle requests to respect max_concurrent_requests per minute.
        """
        async with self._lock:
            now = time.time()
            # Remove requests older than 1 minute
            self.request_times = [t for t in self.request_times if now - t < 60]

            # If we're at the limit, wait until oldest request expires
            if len(self.request_times) >= self.max_concurrent_requests:
                oldest_request = min(self.request_times)
                wait_time = 60 - (now - oldest_request) + 0.1  # Add small buffer
                if wait_time > 0:
                    logger.debug(
                        f"Throttling: {len(self.request_times)} requests in last minute. "
                        f"Waiting {wait_time:.2f}s..."
                    )
                    await asyncio.sleep(wait_time)
                    # Clean up again after waiting
                    now = time.time()
                    self.request_times = [t for t in self.request_times if now - t < 60]

            # Record this request
            self.request_times.append(time.time())


# Singleton instance
_rate_limiter_instance: Optional[FigmaRateLimiter] = None


def get_rate_limiter() -> FigmaRateLimiter:
    """Get or create the singleton rate limiter instance."""
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = FigmaRateLimiter()
    return _rate_limiter_instance
