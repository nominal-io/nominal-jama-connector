from datetime import UTC, datetime

import httpx
import pytest
import respx

from nominal_checks_from_jama._jama import (
    BearerToken,
    JamaClient,
    JamaErrorKind,
    JamaHTTPError,
    instance_url,
    project_in_url,
)

from .conftest import API, BASE, envelope, item


def test_base_url_accepts_rest_v1_and_trailing_slash() -> None:
    with JamaClient(BASE + "/rest/v1/", BearerToken("t")) as jama:
        assert jama.base_url == BASE


def test_base_url_must_be_a_url() -> None:
    with pytest.raises(ValueError, match="Not a Jama Connect URL"):
        JamaClient("ftp://example.jamacloud.com", BearerToken("t"))


@pytest.mark.parametrize(
    ("url", "instance", "project"),
    [
        ("https://example.jamacloud.com", "https://example.jamacloud.com", None),
        ("example.jamacloud.com/", "https://example.jamacloud.com", None),
        ("https://example.jamacloud.com/perspective.req#/home", "https://example.jamacloud.com", None),
        ("https://example.jamacloud.com/perspective.req#/items/56?projectId=12", "https://example.jamacloud.com", "12"),
        ("https://example.jamacloud.com/perspective.req#/projects/60/dashboard", "https://example.jamacloud.com", "60"),
        (
            "https://jama.example.com:8443/contour/perspective.req#/items/5?projectId=7",
            "https://jama.example.com:8443/contour",
            "7",
        ),
    ],
)
def test_instance_url_from_a_pasted_page(url: str, instance: str, project: str | None) -> None:
    assert instance_url(url) == instance
    assert project_in_url(url) == project


def test_headers_and_auth(api: respx.MockRouter, jama: JamaClient) -> None:
    route = api.get("/users/current").respond(json={"data": {"id": 3, "username": "stester"}})
    user = jama.current_user()
    assert user is not None
    assert user.label == "stester"
    request = route.calls.last.request
    assert request.headers["x-jama-date-fields-with-time"] == "true"
    assert request.headers["authorization"] == "Bearer test-token"


def test_items_pages_until_total(api: respx.MockRouter, jama: JamaClient) -> None:
    pages = [envelope([item(i) for i in range(1, 51)], total=60), envelope([item(i) for i in range(51, 61)], total=60)]
    route = api.get("/abstractitems").mock(side_effect=[httpx.Response(200, json=page) for page in pages])
    result = jama.items(12, 34)
    assert len(result) == 60
    assert not result.truncated
    assert result.total == 60
    starts = [call.request.url.params["startAt"] for call in route.calls]
    assert starts == ["0", "50"]
    params = route.calls[0].request.url.params
    assert (params["project"], params["itemType"], params["sortBy"], params["maxResults"]) == (
        "12",
        "34",
        "lastActivityDate.asc",
        "50",
    )


def test_items_advances_by_result_count(api: respx.MockRouter, jama: JamaClient) -> None:
    # Jama leaves out rows the account can't read, so a full page can hold fewer than 50.
    pages = [
        envelope([item(i) for i in range(1, 49)], total=98, result_count=50),
        envelope([item(i) for i in range(51, 99)], total=98, result_count=48),
    ]
    route = api.get("/abstractitems").mock(side_effect=[httpx.Response(200, json=page) for page in pages])
    result = jama.items(12, 34)
    assert [call.request.url.params["startAt"] for call in route.calls] == ["0", "50"]
    assert len(result) == 96
    # Fewer rows than Jama's total: the listing says it didn't read everything.
    assert result.truncated


def test_items_stops_at_max_rows(api: respx.MockRouter, jama: JamaClient) -> None:
    route = api.get("/abstractitems").respond(json=envelope([item(i) for i in range(1, 11)], total=500))
    result = jama.items(12, 34, max_rows=10)
    assert len(result) == 10
    assert result.truncated
    assert route.calls[0].request.url.params["maxResults"] == "10"
    assert route.call_count == 1


def test_items_short_page_without_total_is_complete(api: respx.MockRouter, jama: JamaClient) -> None:
    api.get("/abstractitems").respond(json=envelope([item(1), item(2)]))
    result = jama.items(12, 34)
    assert len(result) == 2
    assert not result.truncated
    assert result.total is None


def test_items_since(api: respx.MockRouter, jama: JamaClient) -> None:
    route = api.get("/abstractitems").respond(json=envelope([]))
    jama.items(12, 34, since=datetime(2026, 10, 1, tzinfo=UTC))
    assert route.calls.last.request.url.params["lastActivityDate"] == "2026-10-01T00:00:00.000Z"


def test_item_types_for_a_project(api: respx.MockRouter, jama: JamaClient) -> None:
    route = api.get("/projects/12/itemtypes").respond(json=envelope([{"id": 34, "display": "Requirement"}]))
    types = jama.item_types(12)
    assert [t.display for t in types] == ["Requirement"]
    assert route.called


def test_item_type_with_fields(api: respx.MockRouter, jama: JamaClient) -> None:
    api.get("/itemtypes/34").respond(
        json={"data": {"id": 34, "display": "Requirement", "fields": [{"name": "name", "fieldType": "STRING"}]}}
    )
    assert [f.name for f in jama.item_type(34).fields] == ["name"]


def test_count_items(api: respx.MockRouter, jama: JamaClient) -> None:
    route = api.get("/abstractitems").respond(json=envelope([item(1)], total=321))
    assert jama.count_items(12, 34) == 321
    assert route.calls.last.request.url.params["maxResults"] == "1"


def test_item_reply_without_id_is_invalid(api: respx.MockRouter, jama: JamaClient) -> None:
    api.get("/items/7").respond(json={"data": {"fields": {}}})
    with pytest.raises(JamaHTTPError) as caught:
        jama.item(7)
    assert caught.value.kind is JamaErrorKind.INVALID_RESPONSE


def test_errors_are_classified_without_the_body(api: respx.MockRouter, jama: JamaClient) -> None:
    api.get("/items/7").respond(404, text="secret echoed by the server")
    with pytest.raises(JamaHTTPError) as caught:
        jama.item(7)
    assert caught.value.kind is JamaErrorKind.NOT_FOUND
    assert caught.value.status == 404
    assert "secret" not in str(caught.value)
    assert str(caught.value) == "GET /rest/v1/items/7 failed: not_found (404)"


def test_item_url() -> None:
    with JamaClient(BASE, BearerToken("t")) as jama:
        assert jama.item_url(12, 345) == f"{BASE}/perspective.req#/items/345?projectId=12"


def test_api_prefix_constant() -> None:
    assert API == BASE + "/rest/v1"
