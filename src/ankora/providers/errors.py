"""Clean provider-error mapping and bounded retry for API calls.

Provider SDK exceptions (openai/anthropic) are noisy and leak tracebacks. This
module maps recognized API failures (429/401/400, connection/timeout) to a
one-line :class:`ProviderError`, retries rate limits a couple of times with
backoff, and re-raises anything it does not recognize (so real bugs are not
masked). Classification is duck-typed on ``status_code`` / class name so we do
not import the heavy SDKs here.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_DELAY = 1.0


class ProviderError(Exception):
    """A provider API call failed. Carries a one-line, user-facing message."""


class ProviderRateLimitError(ProviderError):
    """Raised when a provider keeps rate-limiting after the retry budget."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


def request_with_retry(
    call: Callable[[], T],
    *,
    provider: str,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
) -> T:
    """Run ``call`` with a bounded retry on 429; map other API errors cleanly.

    On a rate limit, retries up to ``max_attempts`` total, sleeping for the
    provider's ``Retry-After`` when present else exponential backoff. Recognized
    non-retryable API errors raise :class:`ProviderError`; unrecognized
    exceptions propagate unchanged.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            return call()
        except Exception as exc:
            mapped = _classify(exc, provider)
            if mapped is None:
                raise  # not a recognized provider API error — do not mask it
            if isinstance(mapped, ProviderRateLimitError) and attempt < max_attempts:
                delay = (
                    mapped.retry_after
                    if mapped.retry_after is not None
                    else base_delay * (2 ** (attempt - 1))
                )
                time.sleep(delay)
                continue
            raise mapped from exc


def _classify(exc: Exception, provider: str) -> ProviderError | None:
    """Map an SDK exception to a clean ProviderError, or None if unrecognized."""
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__

    if status == 429 or name == "RateLimitError":
        retry_after = _retry_after(exc)
        detail = f"Retry in {retry_after:g}s." if retry_after is not None else "Retry shortly."
        return ProviderRateLimitError(
            f"Rate limited by {provider} (429). {detail}",
            retry_after=retry_after,
        )
    if status == 401 or name == "AuthenticationError":
        return ProviderError(f"Provider auth failed (401): check your API key for {provider}.")
    if status == 400 or name == "BadRequestError":
        return ProviderError(f"Provider bad request (400) for {provider}: {_short(exc)}")
    if isinstance(status, int):
        return ProviderError(f"Provider error ({status}) from {provider}: {_short(exc)}")
    if "Connection" in name or "Timeout" in name:
        return ProviderError(f"Could not reach {provider}: {_short(exc)}")
    return None


def _retry_after(exc: Exception) -> float | None:
    """Extract a numeric Retry-After (seconds) from the SDK exception, if any."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    getter = getattr(headers, "get", None)
    if not callable(getter):
        return None
    value: Any = getter("retry-after") or getter("Retry-After")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _short(exc: Exception, limit: int = 200) -> str:
    text = str(exc).strip()
    first = text.splitlines()[0] if text else type(exc).__name__
    return first[:limit]
