"""Ways to sign in to Jama, as :class:`httpx.Auth` objects for the Jama reader."""

from __future__ import annotations

import base64
import time
from collections.abc import Callable, Generator

import httpx

from nominal_checks_from_jama._jama.errors import JamaErrorKind, JamaHTTPError, classify_status
from nominal_checks_from_jama._jama.limits import TOKEN_REFRESH_MARGIN_SECONDS

TOKEN_PATH = "/rest/oauth/token"
"""Where Jama exchanges an API client ID and secret for an access token."""

_API_PREFIX = "/rest/v1/"


class ClientCredentials(httpx.Auth):
    """Signs in with a Jama API client ID and secret, using OAuth client credentials.

    Jama refuses the ID and secret on its REST API itself, so this exchanges them at
    ``/rest/oauth/token`` for an access token and sends that. It fetches a new token shortly before
    the old one expires, and once more if Jama answers 401, then repeats the refused request.
    Jama has no refresh tokens, so each renewal is a new exchange.
    """

    requires_response_body = True

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        *,
        refresh_margin: float = TOKEN_REFRESH_MARGIN_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Create the sign-in.

        Args:
            client_id (str): The API client ID.
            client_secret (str): The API client secret.
            refresh_margin (float): Seconds before the token's stated expiry to fetch a new one.
            clock (Callable[[], float]): A monotonic clock in seconds; tests pass a fake one.
        """
        self._basic = "Basic " + base64.b64encode(f"{client_id}:{client_secret}".encode()).decode("ascii")
        self._refresh_margin = refresh_margin
        self._clock = clock
        self._token: str | None = None
        self._expires_at: float | None = None

    def _stale(self) -> bool:
        if self._token is None:
            return True
        # With no stated lifetime, the token is renewed only when Jama refuses it.
        return self._expires_at is not None and self._clock() >= self._expires_at - self._refresh_margin

    def _token_request(self, request: httpx.Request) -> httpx.Request:
        path = request.url.path
        at = path.find(_API_PREFIX)
        base_path = path[:at] if at >= 0 else ""
        url = request.url.copy_with(path=base_path + TOKEN_PATH, query=None)
        return httpx.Request(
            "POST",
            url,
            data={"grant_type": "client_credentials"},
            headers={"Authorization": self._basic, "Accept": "application/json"},
        )

    def _store(self, response: httpx.Response) -> None:
        if response.status_code != 200:
            # Never the body: a token endpoint can echo the request it refused.
            raise JamaHTTPError(
                classify_status(response.status_code), status=response.status_code, method="POST", path=TOKEN_PATH
            )
        try:
            payload = response.json()
        except ValueError:
            payload = None
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token.strip():
            raise JamaHTTPError(
                JamaErrorKind.INVALID_RESPONSE, status=response.status_code, method="POST", path=TOKEN_PATH
            )
        expires_in = payload.get("expires_in") if isinstance(payload, dict) else None
        self._token = token.strip()
        self._expires_at = (
            self._clock() + float(expires_in)
            if isinstance(expires_in, int | float) and not isinstance(expires_in, bool) and expires_in > 0
            else None
        )

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Add a bearer token, fetching one first when needed, and retry once on a 401.

        Args:
            request (httpx.Request): The request to sign.

        Yields:
            httpx.Request: Token requests as needed, then the signed request.
        """
        if self._stale():
            self._store((yield self._token_request(request)))
        request.headers["Authorization"] = f"Bearer {self._token}"
        response = yield request
        if response.status_code == 401:
            self._store((yield self._token_request(request)))
            request.headers["Authorization"] = f"Bearer {self._token}"
            yield request


class BearerToken(httpx.Auth):
    """Signs in with an access token you already have.

    Nothing renews it, so requests fail with ``unauthorized`` once it expires. Use
    :class:`ClientCredentials` for anything that runs longer than the token lasts.
    """

    def __init__(self, token: str) -> None:
        """Create the sign-in.

        Args:
            token (str): A Jama OAuth access token.
        """
        self._header = f"Bearer {token.strip()}"

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """Add the token to the request.

        Args:
            request (httpx.Request): The request to sign.

        Yields:
            httpx.Request: The signed request.
        """
        request.headers["Authorization"] = self._header
        yield request
