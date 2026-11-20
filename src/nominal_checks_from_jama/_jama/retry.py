"""When a failed request is worth another attempt, and how long to wait first."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

from nominal_checks_from_jama._jama.errors import JamaErrorKind, JamaHTTPError

_TRANSIENT = frozenset({JamaErrorKind.SERVER, JamaErrorKind.UNAVAILABLE, JamaErrorKind.NETWORK, JamaErrorKind.TIMEOUT})
# Methods whose repeat can't do something twice. A POST that timed out may have created the item,
# so it's retried only when Jama said it didn't run it (429).
_IDEMPOTENT = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})


@dataclass(frozen=True)
class RetryPolicy:
    """How :class:`~nominal_checks_from_jama._jama.client.JamaClient` retries failed requests.

    - A 429 is retried with exponential backoff and full jitter, and never sooner than the
      response's ``Retry-After``.
    - Server errors, timeouts and network failures are retried after ``transient_delays``, for
      reads and other repeatable requests only.
    - Other failures, such as 401, 403, 404 and validation errors, aren't retried.

    Attributes:
        max_attempts (int): Attempts per request, the first included.
        base_delay (float): Seconds; the first 429 backoff's upper bound, doubled per attempt.
        max_delay (float): Seconds; the longest single wait, a ``Retry-After`` included.
        transient_delays (tuple[float, ...]): Seconds to wait before each retry of a transient
            failure. Its length is how many such retries a request gets.
        sleep (Callable[[float], None]): Waits the given seconds; tests pass a fake.
        random (Callable[[], float]): Returns a float in [0, 1) for jitter; tests pass a fixed one.
    """

    max_attempts: int = 4
    base_delay: float = 0.5
    max_delay: float = 15.0
    transient_delays: tuple[float, ...] = (0.5, 1.5)
    sleep: Callable[[float], None] = time.sleep
    random: Callable[[], float] = random.random

    def delay(self, error: JamaHTTPError, attempt: int) -> float | None:
        """Seconds to wait before retrying, or None when the failure shouldn't be retried.

        Args:
            error (JamaHTTPError): The failure.
            attempt (int): The attempt that failed, counting from 1.

        Returns:
            float | None: The wait in seconds, or None to give up.
        """
        if attempt >= self.max_attempts:
            return None
        if error.kind is JamaErrorKind.RATE_LIMITED:
            backoff = self.random() * min(self.max_delay, self.base_delay * 2.0 ** (attempt - 1))
            server = _retry_after_seconds(error.retry_after)
            return max(backoff, min(server, self.max_delay)) if server is not None else backoff
        if error.kind in _TRANSIENT and error.method in _IDEMPOTENT and attempt <= len(self.transient_delays):
            return self.transient_delays[attempt - 1]
        return None


def _retry_after_seconds(value: str | None) -> float | None:
    """A ``Retry-After`` header in seconds: either a number or an HTTP date."""
    if not value:
        return None
    text = value.strip()
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())
