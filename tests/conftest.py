"""Shared fixtures. Every name, key and host here is invented."""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import keyring
import pytest
import respx
from keyring.backend import KeyringBackend

from nominal_checks_from_jama._jama import BearerToken, JamaClient, RetryPolicy

if TYPE_CHECKING:
    from .fake_jama import FakeJama

BASE = "https://example.jamacloud.com"
API = BASE + "/rest/v1"


def envelope(
    data: list[dict[str, Any]], *, total: int | None = None, result_count: int | None = None
) -> dict[str, Any]:
    """A Jama list response."""
    page_info: dict[str, Any] = {"resultCount": len(data) if result_count is None else result_count}
    if total is not None:
        page_info["totalResults"] = total
    return {"meta": {"pageInfo": page_info}, "data": data}


def item(item_id: int, **extra: Any) -> dict[str, Any]:
    """An item as Jama sends it."""
    return {
        "id": item_id,
        "documentKey": f"WA-REQ-{item_id}",
        "globalId": f"GID-{item_id}",
        "itemType": 34,
        "version": 2,
        "lastActivityDate": "2026-10-01T14:03:12.000+0000",
        "fields": {"name": f"Requirement {item_id}", "description": "<p>Text</p>"},
        "location": {"parent": {"item": 900}},
        **extra,
    }


class Sleeps:
    """A fake sleep that records the waits."""

    def __init__(self) -> None:
        self.waits: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.waits.append(seconds)


@pytest.fixture
def sleeps() -> Sleeps:
    return Sleeps()


@pytest.fixture
def api() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=API, assert_all_called=False) as router:
        yield router


@pytest.fixture
def jama(sleeps: Sleeps) -> Iterator[JamaClient]:
    client = JamaClient(BASE, BearerToken("test-token"), retry=RetryPolicy(sleep=sleeps, random=lambda: 0.5))
    yield client
    client.close()


class MemoryKeyring(KeyringBackend):
    """A keyring that keeps secrets in a dict."""

    priority = 1

    def __init__(self) -> None:
        super().__init__()  # type: ignore[no-untyped-call]
        self.secrets: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, username: str) -> str | None:
        return self.secrets.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.secrets[(service, username)] = password

    def delete_password(self, service: str, username: str) -> None:
        self.secrets.pop((service, username), None)


@pytest.fixture
def memory_keyring() -> Iterator[MemoryKeyring]:
    previous = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


@pytest.fixture
def fake() -> Iterator[FakeJama]:
    """The invented project, served at BASE, with the client credentials token exchange."""
    from .fake_jama import FakeJama

    jama = FakeJama()
    with respx.mock(base_url=API, assert_all_called=False) as router:
        jama.install(router)
        router.post(BASE + "/rest/oauth/token").respond(json={"access_token": "tok", "expires_in": 3599})
        yield jama
