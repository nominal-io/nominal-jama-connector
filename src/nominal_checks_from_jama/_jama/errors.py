"""The errors the client raises."""

from __future__ import annotations

from enum import StrEnum


class JamaErrorKind(StrEnum):
    """Why a request failed. Classified from the HTTP status or the transport failure alone."""

    UNAUTHORIZED = "unauthorized"
    """401: Jama didn't accept the credentials or token."""
    FORBIDDEN = "forbidden"
    """403: the account can't read or change this."""
    NOT_FOUND = "not_found"
    """404 or 410."""
    RATE_LIMITED = "rate_limited"
    """429: Jama is throttling requests."""
    REJECTED = "rejected"
    """Any other 4xx, such as a write Jama refused as invalid."""
    SERVER = "server"
    """A 5xx other than 502, 503 and 504."""
    UNAVAILABLE = "unavailable"
    """502 or 503: Jama, or a gateway in front of it, isn't answering."""
    TIMEOUT = "timeout"
    """408, 504, or no answer before the client's timeout."""
    NETWORK = "network"
    """The request didn't reach Jama: DNS, connection or TLS failures."""
    INVALID_RESPONSE = "invalid_response"
    """Jama answered 2xx with a body the client can't read."""


_STATUS_KINDS = {
    401: JamaErrorKind.UNAUTHORIZED,
    403: JamaErrorKind.FORBIDDEN,
    404: JamaErrorKind.NOT_FOUND,
    410: JamaErrorKind.NOT_FOUND,
    429: JamaErrorKind.RATE_LIMITED,
    408: JamaErrorKind.TIMEOUT,
    504: JamaErrorKind.TIMEOUT,
    502: JamaErrorKind.UNAVAILABLE,
    503: JamaErrorKind.UNAVAILABLE,
}


def classify_status(status: int) -> JamaErrorKind:
    """The kind of failure an HTTP status means.

    Args:
        status (int): An HTTP status code outside 2xx.

    Returns:
        JamaErrorKind: The failure kind for that status.
    """
    if status in _STATUS_KINDS:
        return _STATUS_KINDS[status]
    return JamaErrorKind.SERVER if status >= 500 else JamaErrorKind.REJECTED


class JamaError(Exception):
    """Base class for the client's errors."""


class JamaHTTPError(JamaError):
    """A request to Jama failed.

    The message names the method, path and kind. It never includes the response body, which can
    echo request headers, and never includes the query string, which can carry item ids and search
    text.

    Attributes:
        kind (JamaErrorKind): Why the request failed.
        status (int | None): The HTTP status, or None when there was no response.
        method (str): The request method, such as ``"GET"``.
        path (str): The request path, without the query string.
        retry_after (str | None): The response's ``Retry-After`` header, when it sent one.
    """

    def __init__(
        self,
        kind: JamaErrorKind,
        *,
        status: int | None,
        method: str,
        path: str,
        retry_after: str | None = None,
    ) -> None:
        """Create the error; the client raises these, so callers rarely need to.

        Args:
            kind (JamaErrorKind): Why the request failed.
            status (int | None): The HTTP status, or None when there was no response.
            method (str): The request method.
            path (str): The request path, without the query string.
            retry_after (str | None): The ``Retry-After`` header, if any.

        Example:
            >>> error = JamaHTTPError(JamaErrorKind.NOT_FOUND, status=404, method="GET", path="/rest/v1/items/7")
            >>> str(error)
            'GET /rest/v1/items/7 failed: not_found (404)'
        """
        detail = "" if status is None else f" ({status})"
        super().__init__(f"{method} {path} failed: {kind}{detail}")
        self.kind = kind
        self.status = status
        self.method = method
        self.path = path
        self.retry_after = retry_after
