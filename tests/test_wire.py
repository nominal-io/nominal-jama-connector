from datetime import UTC, datetime

import pytest

from nominal_checks_from_jama._jama import _wire

from .conftest import item


@pytest.mark.parametrize(
    ("value", "expected"),
    [(5, "5"), ("5", "5"), (" 7 ", "7"), (5.0, "5"), (5.5, None), (True, None), ({}, None), ("", None), (None, None)],
)
def test_jama_id(value: object, expected: str | None) -> None:
    assert _wire.jama_id(value) == expected


def test_parse_item() -> None:
    parsed = _wire.parse_item(item(12))
    assert parsed is not None
    assert parsed.id == "12"
    assert parsed.document_key == "WA-REQ-12"
    assert parsed.item_type_id == "34"
    assert parsed.version == "2"
    assert parsed.parent_item_id == "900"
    assert parsed.modified_at == datetime(2026, 10, 1, 14, 3, 12, tzinfo=UTC)
    assert parsed.name == "Requirement 12"


def test_parse_item_without_id_is_dropped_and_counted() -> None:
    page = _wire.envelope(
        {"data": [item(1), {"fields": {}}], "meta": {"pageInfo": {"resultCount": 2}}}, _wire.parse_item
    )
    assert [row.id for row in page.rows] == ["1"]
    assert page.dropped == 1
    assert page.result_count == 2


def test_parse_item_falls_back_to_modified_date() -> None:
    parsed = _wire.parse_item({"id": 1, "modifiedDate": "2026-09-30T08:00:00Z"})
    assert parsed is not None
    assert parsed.modified_at == datetime(2026, 9, 30, 8, tzinfo=UTC)
    assert parsed.parent_item_id is None


def test_parse_item_type_fields() -> None:
    parsed = _wire.parse_item_type(
        {
            "id": 34,
            "typeKey": "REQ",
            "display": "Requirement",
            "fields": [
                {"name": "status$34", "label": "Status", "fieldType": "lookup", "pickList": 77, "required": True},
                {"label": "no name"},
            ],
        }
    )
    assert parsed is not None
    assert parsed.display_plural == "Requirement"
    assert len(parsed.fields) == 1
    field = parsed.fields[0]
    assert (field.name, field.field_type, field.picklist_id, field.required, field.read_only) == (
        "status$34",
        "LOOKUP",
        "77",
        True,
        False,
    )


def test_parse_project_reads_fields() -> None:
    parsed = _wire.parse_project({"id": 12, "fields": {"name": "Widget Assembly", "projectKey": "WA"}})
    assert parsed is not None
    assert (parsed.name, parsed.project_key) == ("Widget Assembly", "WA")


def test_user_label() -> None:
    assert _wire.parse_user({"id": 1, "firstName": "Sam", "lastName": "Tester"}).label == "Sam Tester"  # type: ignore[union-attr]
    assert _wire.parse_user({"id": 1, "username": "stester"}).label == "stester"  # type: ignore[union-attr]
