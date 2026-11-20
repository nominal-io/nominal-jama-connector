"""Reading Jama's JSON into the models.

A row the client can't use, such as one without an id, is dropped and counted rather than guessed
at, so a listing can say how many it skipped.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from nominal_checks_from_jama._jama.models import Item, ItemType, ItemTypeField, Project, User

T = TypeVar("T")


def jama_id(value: object) -> str | None:
    """A Jama id as a string, or None when the value can't be one.

    Jama sends ids as numbers on most endpoints and as strings on a few. ``str(value)`` would turn
    an object into ``"{...}"``, an id that matches nothing, so only finite integers and non-empty
    strings count.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _record(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _datetime(value: object) -> datetime | None:
    text = _text(value)
    if text is None:
        return None
    # Jama writes offsets as +0000; fromisoformat reads that from 3.11 on, and Z too.
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class Page(Generic[T]):
    """One page of a listing, with what Jama said about the whole set."""

    rows: list[T]
    result_count: int
    total_results: int | None
    dropped: int


def envelope(payload: object, parse_row: Callable[[object], T | None]) -> Page[T]:
    """Read a list response: ``data`` plus ``meta.pageInfo``."""
    body = _record(payload)
    page_info = _record(_record(body.get("meta")).get("pageInfo"))
    raw = body.get("data")
    raw_rows: list[object] = raw if isinstance(raw, list) else []
    rows = [row for row in (parse_row(r) for r in raw_rows) if row is not None]
    result_count = page_info.get("resultCount")
    total = page_info.get("totalResults")
    return Page(
        rows=rows,
        result_count=result_count if isinstance(result_count, int) else len(raw_rows),
        total_results=total if isinstance(total, int) else None,
        dropped=len(raw_rows) - len(rows),
    )


def single(payload: object) -> dict[str, Any]:
    """Read a single-object response. Jama wraps most in ``{"data": ...}`` and sends a few bare."""
    body = _record(payload)
    data = body.get("data")
    return data if isinstance(data, dict) else body


def parse_item(value: object) -> Item | None:
    """An item, or None when it has no usable id."""
    raw = _record(value)
    item_id = jama_id(raw.get("id"))
    if item_id is None:
        return None
    parent = _record(_record(raw.get("location")).get("parent"))
    fields = raw.get("fields")
    return Item(
        id=item_id,
        document_key=_text(raw.get("documentKey")),
        global_id=_text(raw.get("globalId")),
        item_type_id=jama_id(raw.get("itemType")),
        version=jama_id(raw.get("version")),
        modified_at=_datetime(raw.get("lastActivityDate")) or _datetime(raw.get("modifiedDate")),
        fields=fields if isinstance(fields, dict) else {},
        parent_item_id=jama_id(parent.get("item")),
    )


def _parse_item_type_field(value: object) -> ItemTypeField | None:
    raw = _record(value)
    name = _text(raw.get("name"))
    if name is None:
        return None
    return ItemTypeField(
        name=name,
        label=_text(raw.get("label")) or name,
        field_type=(_text(raw.get("fieldType")) or "").upper(),
        read_only=raw.get("readOnly") is True,
        required=raw.get("required") is True,
        picklist_id=jama_id(raw.get("pickList")),
    )


def parse_item_type(value: object) -> ItemType | None:
    """An item type, with its fields when the response includes them."""
    raw = _record(value)
    type_id = jama_id(raw.get("id"))
    if type_id is None:
        return None
    type_key = _text(raw.get("typeKey")) or ""
    display = _text(raw.get("display")) or type_key or type_id
    raw_fields = raw.get("fields")
    fields = (
        tuple(f for f in (_parse_item_type_field(v) for v in raw_fields) if f is not None)
        if isinstance(raw_fields, list)
        else ()
    )
    return ItemType(
        id=type_id,
        type_key=type_key,
        display=display,
        display_plural=_text(raw.get("displayPlural")) or display,
        category=_text(raw.get("category")),
        fields=fields,
    )


def parse_project(value: object) -> Project | None:
    """A project. Its name and key are under ``fields`` on most deployments."""
    raw = _record(value)
    project_id = jama_id(raw.get("id"))
    if project_id is None:
        return None
    fields = _record(raw.get("fields"))
    return Project(
        id=project_id,
        name=_text(fields.get("name")) or _text(raw.get("name")) or project_id,
        project_key=_text(fields.get("projectKey")) or _text(raw.get("projectKey")),
    )


def parse_user(value: object) -> User | None:
    """A user, labelled by full name or else username."""
    raw = _record(value)
    user_id = jama_id(raw.get("id"))
    if user_id is None:
        return None
    full = f"{_text(raw.get('firstName')) or ''} {_text(raw.get('lastName')) or ''}".strip()
    return User(id=user_id, label=full or _text(raw.get("username")) or user_id)
