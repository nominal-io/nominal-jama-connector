import httpx
import pytest
import respx

from nominal_checks_from_jama._jama import JamaClient, JamaErrorKind, JamaHTTPError, RetryPolicy

from .conftest import Sleeps, envelope


def test_429_is_retried_after_retry_after(api: respx.MockRouter, jama: JamaClient, sleeps: Sleeps) -> None:
    api.get("/projects").mock(
        side_effect=[httpx.Response(429, headers={"Retry-After": "3"}), httpx.Response(200, json=envelope([]))]
    )
    jama.projects()
    # The backoff (0.5 * 0.5 s) is shorter than Retry-After, so Retry-After wins.
    assert sleeps.waits == [3.0]


def test_429_backoff_doubles(api: respx.MockRouter, jama: JamaClient, sleeps: Sleeps) -> None:
    api.get("/projects").mock(
        side_effect=[httpx.Response(429), httpx.Response(429), httpx.Response(200, json=envelope([]))]
    )
    jama.projects()
    assert sleeps.waits == [0.25, 0.5]


def test_retry_after_is_capped(sleeps: Sleeps) -> None:
    policy = RetryPolicy(sleep=sleeps, random=lambda: 0.0)
    error = JamaHTTPError(JamaErrorKind.RATE_LIMITED, status=429, method="GET", path="/p", retry_after="600")
    assert policy.delay(error, 1) == 15.0


def test_server_errors_are_retried_twice_then_raised(api: respx.MockRouter, jama: JamaClient, sleeps: Sleeps) -> None:
    route = api.get("/projects").respond(500)
    with pytest.raises(JamaHTTPError) as caught:
        jama.projects()
    assert caught.value.kind is JamaErrorKind.SERVER
    assert route.call_count == 3
    assert sleeps.waits == [0.5, 1.5]


def test_not_found_is_not_retried(api: respx.MockRouter, jama: JamaClient, sleeps: Sleeps) -> None:
    route = api.get("/projects/9").respond(404)
    with pytest.raises(JamaHTTPError):
        jama.project(9)
    assert route.call_count == 1
    assert sleeps.waits == []


def test_timeout_is_classified_and_retried(api: respx.MockRouter, jama: JamaClient, sleeps: Sleeps) -> None:
    api.get("/projects").mock(side_effect=[httpx.ReadTimeout("slow"), httpx.Response(200, json=envelope([]))])
    jama.projects()
    assert sleeps.waits == [0.5]


def test_network_failure_kind(api: respx.MockRouter, jama: JamaClient) -> None:
    api.get("/projects").mock(side_effect=httpx.ConnectError("no route"))
    with pytest.raises(JamaHTTPError) as caught:
        jama.projects()
    assert caught.value.kind is JamaErrorKind.NETWORK


def test_post_is_retried_only_on_429() -> None:
    policy = RetryPolicy()
    server = JamaHTTPError(JamaErrorKind.SERVER, status=500, method="POST", path="/rest/v1/items")
    throttled = JamaHTTPError(JamaErrorKind.RATE_LIMITED, status=429, method="POST", path="/rest/v1/items")
    assert policy.delay(server, 1) is None
    assert policy.delay(throttled, 1) is not None


def test_gives_up_after_max_attempts() -> None:
    policy = RetryPolicy(random=lambda: 0.5)
    throttled = JamaHTTPError(JamaErrorKind.RATE_LIMITED, status=429, method="GET", path="/p")
    assert policy.delay(throttled, 3) is not None
    assert policy.delay(throttled, 4) is None
