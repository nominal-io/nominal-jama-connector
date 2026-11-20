import base64

import httpx
import pytest
import respx

from nominal_checks_from_jama._jama import ClientCredentials, JamaClient, JamaErrorKind, JamaHTTPError

from .conftest import BASE, envelope

TOKEN_URL = BASE + "/rest/oauth/token"


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def client(clock: Clock) -> JamaClient:
    return JamaClient(BASE, ClientCredentials("client-a", "secret-b", clock=clock))


def token(value: str, expires_in: int | None = 3599) -> httpx.Response:
    body: dict[str, object] = {"access_token": value, "token_type": "bearer"}
    if expires_in is not None:
        body["expires_in"] = expires_in
    return httpx.Response(200, json=body)


def test_mints_once_and_reuses(client: JamaClient) -> None:
    with respx.mock(assert_all_called=False) as router:
        mint = router.post(TOKEN_URL).mock(return_value=token("tok-1"))
        projects = router.get(BASE + "/rest/v1/projects").respond(json=envelope([]))
        client.projects()
        client.projects()
    assert mint.call_count == 1
    request = mint.calls.last.request
    expected = "Basic " + base64.b64encode(b"client-a:secret-b").decode()
    assert request.headers["authorization"] == expected
    assert request.content == b"grant_type=client_credentials"
    assert projects.calls.last.request.headers["authorization"] == "Bearer tok-1"


def test_refreshes_before_expiry(client: JamaClient, clock: Clock) -> None:
    with respx.mock(assert_all_called=False) as router:
        mint = router.post(TOKEN_URL).mock(side_effect=[token("tok-1"), token("tok-2")])
        projects = router.get(BASE + "/rest/v1/projects").respond(json=envelope([]))
        client.projects()
        clock.now += 3599 - 59  # inside the 60-second margin
        client.projects()
    assert mint.call_count == 2
    assert projects.calls.last.request.headers["authorization"] == "Bearer tok-2"


def test_refreshes_once_on_401_and_repeats_the_request(client: JamaClient) -> None:
    with respx.mock(assert_all_called=False) as router:
        mint = router.post(TOKEN_URL).mock(side_effect=[token("tok-1"), token("tok-2")])
        projects = router.get(BASE + "/rest/v1/projects").mock(
            side_effect=[httpx.Response(401), httpx.Response(200, json=envelope([]))]
        )
        client.projects()
    assert mint.call_count == 2
    assert [call.request.headers["authorization"] for call in projects.calls] == ["Bearer tok-1", "Bearer tok-2"]


def test_without_expiry_renews_only_on_refusal(client: JamaClient, clock: Clock) -> None:
    with respx.mock(assert_all_called=False) as router:
        mint = router.post(TOKEN_URL).mock(return_value=token("tok-1", expires_in=None))
        router.get(BASE + "/rest/v1/projects").respond(json=envelope([]))
        client.projects()
        clock.now += 100_000
        client.projects()
    assert mint.call_count == 1


def test_refused_credentials_raise_without_the_body(client: JamaClient) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.post(TOKEN_URL).respond(401, text="client-a:secret-b rejected")
        with pytest.raises(JamaHTTPError) as caught:
            client.projects()
    assert caught.value.kind is JamaErrorKind.UNAUTHORIZED
    assert caught.value.path == "/rest/oauth/token"
    assert "secret" not in str(caught.value)


def test_token_reply_without_token_is_invalid(client: JamaClient) -> None:
    with respx.mock(assert_all_called=False) as router:
        router.post(TOKEN_URL).respond(json={"token_type": "bearer"})
        with pytest.raises(JamaHTTPError) as caught:
            client.projects()
    assert caught.value.kind is JamaErrorKind.INVALID_RESPONSE


def test_token_path_keeps_a_base_path(clock: Clock) -> None:
    # Self-hosted instances can sit under a path, such as https://host/jama.
    jama = JamaClient(BASE + "/jama", ClientCredentials("a", "b", clock=clock))
    with respx.mock(assert_all_called=False) as router:
        mint = router.post(BASE + "/jama/rest/oauth/token").mock(return_value=token("tok"))
        router.get(BASE + "/jama/rest/v1/projects").respond(json=envelope([]))
        jama.projects()
    assert mint.called
