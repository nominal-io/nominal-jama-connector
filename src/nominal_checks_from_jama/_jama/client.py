"""A read-only client for the Jama Connect REST API."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Self, TypeVar

import httpx

from nominal_checks_from_jama._jama import _wire
from nominal_checks_from_jama._jama.auth import BearerToken, ClientCredentials
from nominal_checks_from_jama._jama.errors import JamaErrorKind, JamaHTTPError, classify_status
from nominal_checks_from_jama._jama.limits import MAX_PAGES_PER_LIST, PAGE_SIZE, REQUEST_TIMEOUT_SECONDS
from nominal_checks_from_jama._jama.models import Item, ItemType, ListResult, Project, User
from nominal_checks_from_jama._jama.retry import RetryPolicy

T = TypeVar("T")

API_PREFIX = "/rest/v1"

# Without x-jama-date-fields-with-time, Jama truncates date fields to midnight in the server's
# timezone, and an incremental read by modification time re-reads or skips items.
_HEADERS = {"Accept": "application/json", "x-jama-date-fields-with-time": "true"}

Id = int | str
"""A Jama id. The client accepts ints or strings and returns strings."""


def _id(value: Id) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError("A Jama id can't be empty.")
    return text


# an item's page has ?projectId=60; the project's own pages have /projects/60/
_PROJECT_IN_URL = re.compile(r"[?&]projectId=(\d+)|/projects/(\d+)(?=[/?#]|$)")


def instance_url(url: str) -> str:
    """The Jama instance's URL, from it or from the URL of any page on it.

    Args:
        url (str): Such as ``https://example.jamacloud.com``, or a page copied from the browser,
            such as ``https://example.jamacloud.com/perspective.req#/items/56?projectId=12``.
            Without a scheme, it's https.

    Returns:
        str: The URL up to ``/perspective.req`` or ``/rest/v1``, without a trailing slash.

    Raises:
        ValueError: When ``url`` isn't an http or https URL.
    """
    text = url.strip()
    if text and "://" not in text:
        text = f"https://{text}"
    try:
        parsed = httpx.URL(text)
    except httpx.InvalidURL:
        parsed = httpx.URL()
    if parsed.scheme not in ("https", "http") or not parsed.host:
        raise ValueError(f"Not a Jama Connect URL: {url!r}. Copy the URL from your browser while Jama Connect is open.")
    path = parsed.path
    for end in ("/perspective.req", API_PREFIX):
        if end in path:
            path = path[: path.index(end)]
    return str(parsed.copy_with(path=path.rstrip("/") or "/", query=None, fragment=None)).rstrip("/")


def project_in_url(url: str) -> str | None:
    """The project id in the URL of a Jama page, such as a requirement's or the project's, or None if it has none."""
    found = _PROJECT_IN_URL.search(url)
    return (found.group(1) or found.group(2)) if found else None


def _since(value: str | datetime) -> str:
    if isinstance(value, str):
        return value
    when = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return when.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class JamaClient:
    """A read-only client for the Jama Connect REST API.

    Listings read every page and return a :class:`~nominal_checks_from_jama._jama.models.ListResult`,
    which says whether it stopped early. Failed requests raise
    :class:`~nominal_checks_from_jama._jama.errors.JamaHTTPError`; rate-limited and transient failures
    are retried first, as :class:`~nominal_checks_from_jama._jama.retry.RetryPolicy` describes.

    A client holds a connection pool: close it when you're done, or use it in a ``with`` block.
    """

    def __init__(
        self,
        base_url: str,
        auth: httpx.Auth,
        *,
        timeout: float = REQUEST_TIMEOUT_SECONDS,
        retry: RetryPolicy | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Create a client.

        Args:
            base_url (str): The Jama instance's URL, such as ``"https://example.jamacloud.com"``, or
                the URL of any page on it. See :func:`instance_url`.
            auth (httpx.Auth): How to sign in: :class:`~nominal_checks_from_jama._jama.auth.ClientCredentials`,
                :class:`~nominal_checks_from_jama._jama.auth.BearerToken`, or :class:`httpx.BasicAuth`
                with a username and password. Basic sign-in doesn't work on instances that use single
                sign-on.
            timeout (float): Seconds each request may take.
            retry (RetryPolicy | None): Retry rules; the defaults when None.
            transport (httpx.BaseTransport | None): A custom transport, such as a mock in tests.
        """
        self._base_url = instance_url(base_url)
        self._retry = retry or RetryPolicy()
        self._http = httpx.Client(
            base_url=self._base_url + API_PREFIX,
            auth=auth,
            headers=_HEADERS,
            timeout=timeout,
            transport=transport,
        )

    @classmethod
    def from_client_credentials(cls, base_url: str, client_id: str, client_secret: str, **kwargs: Any) -> Self:
        """A client that signs in with an API client ID and secret.

        Args:
            base_url (str): The Jama instance's URL.
            client_id (str): The API client ID.
            client_secret (str): The API client secret.
            **kwargs (Any): Passed to :class:`JamaClient`.

        Returns:
            JamaClient: The client.
        """
        return cls(base_url, ClientCredentials(client_id, client_secret), **kwargs)

    @classmethod
    def from_basic(cls, base_url: str, username: str, password: str, **kwargs: Any) -> Self:
        """A client that signs in with a username and password.

        Args:
            base_url (str): The Jama instance's URL.
            username (str): The Jama username.
            password (str): The password.
            **kwargs (Any): Passed to :class:`JamaClient`.

        Returns:
            JamaClient: The client.
        """
        return cls(base_url, httpx.BasicAuth(username, password), **kwargs)

    @classmethod
    def from_token(cls, base_url: str, token: str, **kwargs: Any) -> Self:
        """A client that signs in with an access token you already have, which nothing renews.

        Args:
            base_url (str): The Jama instance's URL.
            token (str): A Jama OAuth access token.
            **kwargs (Any): Passed to :class:`JamaClient`.

        Returns:
            JamaClient: The client.
        """
        return cls(base_url, BearerToken(token), **kwargs)

    @property
    def base_url(self) -> str:
        """The Jama instance's URL, as the client uses it.

        Returns:
            str: The URL, without a trailing slash.
        """
        return self._base_url

    def close(self) -> None:
        """Close the client's connections."""
        self._http.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        self.close()

    # -- requests ------------------------------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        parse: Callable[[object, httpx.Response], T],
        *,
        params: Mapping[str, str | int] | None = None,
    ) -> T:
        full_path = API_PREFIX + path
        attempt = 0
        while True:
            attempt += 1
            try:
                return self._attempt(method, path, full_path, parse, params)
            except JamaHTTPError as error:
                wait = self._retry.delay(error, attempt)
                if wait is None:
                    raise
                self._retry.sleep(wait)

    def _attempt(
        self,
        method: str,
        path: str,
        full_path: str,
        parse: Callable[[object, httpx.Response], T],
        params: Mapping[str, str | int] | None,
    ) -> T:
        try:
            response = self._http.request(method, path, params=params)
        except httpx.TimeoutException:
            raise JamaHTTPError(JamaErrorKind.TIMEOUT, status=None, method=method, path=full_path) from None
        except httpx.TransportError:
            raise JamaHTTPError(JamaErrorKind.NETWORK, status=None, method=method, path=full_path) from None
        if not response.is_success:
            raise JamaHTTPError(
                classify_status(response.status_code),
                status=response.status_code,
                method=method,
                path=full_path,
                retry_after=response.headers.get("retry-after"),
            )
        try:
            payload: object = response.json() if response.content.strip() else {}
            return parse(payload, response)
        except (ValueError, TypeError):
            raise JamaHTTPError(
                JamaErrorKind.INVALID_RESPONSE, status=response.status_code, method=method, path=full_path
            ) from None

    def _get_one(self, path: str, parse_row: Callable[[object], T | None], what: str) -> T:
        def parse(payload: object, _: httpx.Response) -> T:
            row = parse_row(_wire.single(payload))
            if row is None:
                raise ValueError(f"The {what} reply had no id.")
            return row

        return self._request("GET", path, parse)

    def _list(
        self,
        path: str,
        parse_row: Callable[[object], T | None],
        *,
        params: Mapping[str, str | int] | None = None,
        max_rows: int | None = None,
    ) -> ListResult[T]:
        """Read every page of an offset-paged (``startAt``/``maxResults``) listing.

        It stops at the first of: an empty or short page, the total Jama reported, ``max_rows``,
        a page that doesn't move the cursor, or
        :data:`~nominal_checks_from_jama._jama.limits.MAX_PAGES_PER_LIST`. ``startAt`` advances by
        the rows Jama says it sent, not by the page size, because Jama leaves out rows the account
        can't read.
        """
        rows: list[T] = []
        dropped = 0
        total: int | None = None
        start_at = 0

        def result(truncated: bool) -> ListResult[T]:
            return ListResult(tuple(rows), truncated, total, dropped)

        def swept() -> bool:
            return total is None or len(rows) >= total

        for _ in range(MAX_PAGES_PER_LIST):
            remaining = PAGE_SIZE if max_rows is None else max_rows - len(rows)
            if remaining <= 0:
                return result(True)
            size = min(PAGE_SIZE, remaining)
            page = self._request(
                "GET",
                path,
                lambda payload, _: _wire.envelope(payload, parse_row),
                params={**(params or {}), "startAt": start_at, "maxResults": size},
            )
            rows.extend(page.rows)
            dropped += page.dropped
            if page.total_results is not None:
                total = page.total_results
            if page.result_count == 0:
                return result(not swept())
            if page.result_count < 0:
                # A count that would move the cursor backwards; the listing can't continue.
                return result(True)
            start_at += page.result_count
            if page.result_count < size or (total is not None and start_at >= total):
                return result(not swept())
        return result(True)

    # -- reads -----------------------------------------------------------------------------------

    def current_user(self) -> User | None:
        """The user the client is signed in as.

        Returns:
            User | None: The user, or None when Jama's reply had no id.
        """
        return self._request("GET", "/users/current", lambda payload, _: _wire.parse_user(_wire.single(payload)))

    def projects(self, *, max_rows: int | None = None) -> ListResult[Project]:
        """The projects the account can read.

        Args:
            max_rows (int | None): Stop after this many; all of them when None.

        Returns:
            ListResult[Project]: The projects.
        """
        return self._list("/projects", _wire.parse_project, max_rows=max_rows)

    def project(self, project_id: Id) -> Project:
        """One project.

        Args:
            project_id (int | str): The project id.

        Returns:
            Project: The project.
        """
        return self._get_one(f"/projects/{_id(project_id)}", _wire.parse_project, "project")

    def item_types(self, project: Id | None = None, *, max_rows: int | None = None) -> ListResult[ItemType]:
        """Item types, without their fields; :meth:`item_type` returns those.

        Args:
            project (int | str | None): Only the types this project uses; every type when None.
            max_rows (int | None): Stop after this many; all of them when None.

        Returns:
            ListResult[ItemType]: The item types.
        """
        path = "/itemtypes" if project is None else f"/projects/{_id(project)}/itemtypes"
        return self._list(path, _wire.parse_item_type, max_rows=max_rows)

    def item_type(self, item_type_id: Id) -> ItemType:
        """One item type, with its fields.

        Args:
            item_type_id (int | str): The item type id.

        Returns:
            ItemType: The item type.
        """
        return self._get_one(f"/itemtypes/{_id(item_type_id)}", _wire.parse_item_type, "item type")

    def count_items(self, project: Id, item_type: Id) -> int | None:
        """How many items of a type a project has, read without listing them.

        Args:
            project (int | str): The project id.
            item_type (int | str): The item type id.

        Returns:
            int | None: The count, or None when Jama didn't report one.
        """
        page = self._request(
            "GET",
            "/abstractitems",
            lambda payload, _: _wire.envelope(payload, _wire.parse_item),
            params={"project": _id(project), "itemType": _id(item_type), "maxResults": 1},
        )
        return page.total_results

    def items(
        self,
        project: Id,
        item_type: Id,
        *,
        since: str | datetime | None = None,
        max_rows: int | None = None,
    ) -> ListResult[Item]:
        """A project's items of one type, oldest change first.

        Args:
            project (int | str): The project id.
            item_type (int | str): The item type id.
            since (str | datetime | None): Only items changed at or after this time: a datetime
                (naive ones are taken as UTC), or an ISO 8601 string Jama accepts.
            max_rows (int | None): Stop after this many; all of them when None.

        Returns:
            ListResult[Item]: The items.
        """
        params: dict[str, str | int] = {
            "project": _id(project),
            "itemType": _id(item_type),
            # A fixed order, so offset paging doesn't skip or repeat items edited during the read.
            "sortBy": "lastActivityDate.asc",
        }
        if since is not None:
            params["lastActivityDate"] = _since(since)
        return self._list("/abstractitems", _wire.parse_item, params=params, max_rows=max_rows)

    def item(self, item_id: Id) -> Item:
        """One item.

        Args:
            item_id (int | str): The item id.

        Returns:
            Item: The item.
        """
        return self._get_one(f"/items/{_id(item_id)}", _wire.parse_item, "item")

    def item_url(self, project: Id, item_id: Id) -> str:
        """The URL of an item in Jama's web interface.

        Args:
            project (int | str): The item's project id.
            item_id (int | str): The item id.

        Returns:
            str: The item's URL.
        """
        return f"{self._base_url}/perspective.req#/items/{_id(item_id)}?projectId={_id(project)}"
