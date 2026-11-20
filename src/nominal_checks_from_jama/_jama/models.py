"""What the Jama reader returns. Every Jama id is a string, whatever type Jama sent it as."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Project:
    """A Jama project.

    Attributes:
        id (str): The project id.
        name (str): The project name.
        project_key (str | None): The key in its items' document keys, such as ``"PRJ"``.
    """

    id: str
    name: str
    project_key: str | None


@dataclass(frozen=True, slots=True)
class User:
    """A Jama user.

    Attributes:
        id (str): The user id.
        label (str): The user's full name, or their username when Jama has no name for them.
    """

    id: str
    label: str


@dataclass(frozen=True, slots=True)
class ItemTypeField:
    """One field of a Jama item type.

    Attributes:
        name (str): The key in an item's ``fields``: ``"name"`` for a system field, and a name
            with a suffix such as ``"status$123"`` for a custom one.
        label (str): The field's label in Jama.
        field_type (str): Jama's field type in upper case, such as ``"TEXT"`` or ``"LOOKUP"``.
        read_only (bool): Whether Jama refuses writes to the field.
        required (bool): Whether Jama requires a value.
        picklist_id (str | None): The picklist a LOOKUP or MULTI_LOOKUP field draws from.
    """

    name: str
    label: str
    field_type: str
    read_only: bool
    required: bool
    picklist_id: str | None


@dataclass(frozen=True, slots=True)
class ItemType:
    """A Jama item type, such as "Requirement" or "Test Case".

    Attributes:
        id (str): The item type id.
        type_key (str): Jama's short key for the type, such as ``"REQ"``.
        display (str): The type's name.
        display_plural (str): The type's plural name.
        category (str | None): Jama's category for the type, when it gives one.
        fields (tuple[ItemTypeField, ...]): The type's fields. Only
            :meth:`~nominal_checks_from_jama._jama.client.JamaClient.item_type` returns them;
            listings leave this empty.
    """

    id: str
    type_key: str
    display: str
    display_plural: str
    category: str | None
    fields: tuple[ItemTypeField, ...] = ()


@dataclass(frozen=True, slots=True)
class Item:
    """A Jama item.

    Attributes:
        id (str): The item id.
        document_key (str | None): The item's key in its project, such as ``"PRJ-REQ-12"``.
        global_id (str | None): The id that follows the item across projects and reuse.
        item_type_id (str | None): The item's type.
        version (str | None): The item's version number.
        modified_at (datetime | None): When the item last changed, in UTC.
        fields (Mapping[str, Any]): The item's field values, keyed by field name. TEXT fields
            hold HTML; LOOKUP fields hold picklist option ids.
        parent_item_id (str | None): The item this one sits under, or None at the project root.
    """

    id: str
    document_key: str | None
    global_id: str | None
    item_type_id: str | None
    version: str | None
    modified_at: datetime | None
    fields: Mapping[str, Any] = field(default_factory=dict)
    parent_item_id: str | None = None

    @property
    def name(self) -> str | None:
        """The item's ``name`` field, or None when it has none.

        Returns:
            str | None: The name.
        """
        value = self.fields.get("name")
        return value if isinstance(value, str) else None


@dataclass(frozen=True, slots=True)
class ListResult(Generic[T]):
    """The rows a listing read, and whether it read all of them.

    Iterate over it, index it or take its ``len()`` as you would a list of rows.

    Attributes:
        rows (tuple[T, ...]): The rows read.
        truncated (bool): True when the listing stopped before the end of the set: at
            ``max_rows``, at the page limit, or because Jama's paging stopped advancing.
        total (int | None): The size of the whole set as Jama reported it, or None when it
            didn't say.
        dropped (int): Rows Jama sent without a usable id, which the client skipped.
    """

    rows: tuple[T, ...]
    truncated: bool
    total: int | None
    dropped: int

    def __iter__(self) -> Iterator[T]:
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> T:
        return self.rows[index]
