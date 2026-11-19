"""Retry with exponential backoff for flaky source APIs."""

from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

import httpx

from .logging_utils import log

T = TypeVar("T")

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class RetryableHTTPError(Exception):
    def __init__(self, response: httpx.Response):
        super().__init__(f"HTTP {response.status_code} from {response.request.url}")
        self.response = response


def raise_for_retryable(response: httpx.Response) -> httpx.Response:
    """Turn retryable statuses into RetryableHTTPError; other errors raise immediately."""
    if response.status_code in RETRYABLE_STATUS:
        raise RetryableHTTPError(response)
    response.raise_for_status()
    return response


def with_retries(
    fn: Callable[[], T],
    *,
    attempts: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    sleep: Callable[[float], None] | None = None,
) -> T:
    """Call ``fn`` until it succeeds, backing off on transport errors and retryable statuses.

    Honours ``Retry-After`` on 429/503 when the source sends it.
    """
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except (httpx.TransportError, RetryableHTTPError) as exc:
            if attempt == attempts:
                log("retry_exhausted", "ERROR", attempts=attempts, error=str(exc))
                raise
            delay = min(max_delay, base_delay * 2 ** (attempt - 1)) + random.uniform(0, 0.5)
            if isinstance(exc, RetryableHTTPError):
                retry_after = exc.response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = min(max_delay, float(retry_after))
            log("retrying", "WARNING", attempt=attempt, delay_s=round(delay, 2), error=str(exc))
            (sleep or time.sleep)(delay)
    raise AssertionError("unreachable")
