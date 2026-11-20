"""Reading a Jama project's item types, and proposing which hold requirements."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from nominal_checks_from_jama._jama import ItemType, JamaClient, Project


class TypeCategory(StrEnum):
    """What a Jama item type holds, as far as its category, key and name say."""

    REQUIREMENT = "requirement"
    TEST_CASE = "test case"
    """Types Jama uses as test cases, with test steps."""
    CONTAINER = "container"
    """Sets, folders, text and components: where items are kept, not requirements."""
    OTHER = "other"


_CATEGORY_TOKENS = {
    "REQUIREMENT": TypeCategory.REQUIREMENT,
    "REQUIREMENTS": TypeCategory.REQUIREMENT,
    "TEST_CASE": TypeCategory.TEST_CASE,
    "TEST_CASES": TypeCategory.TEST_CASE,
    **dict.fromkeys(
        ["SET", "SETS", "SECTION", "SECTIONS", "FOLDER", "FOLDERS", "TEXT", "TEXTS", "COMPONENT", "COMPONENTS"],
        TypeCategory.CONTAINER,
    ),
}
# Jama's stock type keys
_TYPE_KEYS = {
    "SET": TypeCategory.CONTAINER,
    "FLD": TypeCategory.CONTAINER,
    "TXT": TypeCategory.CONTAINER,
    "CMP": TypeCategory.CONTAINER,
    "REQ": TypeCategory.REQUIREMENT,
}
# The last word of the name: "System Requirement" is a requirement, "Requirement Set" isn't.
_REQUIREMENT_NAME = re.compile(r"(^|\s)requirements?$", re.IGNORECASE)


def _token(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", value.strip().upper()).strip("_")


def type_category(item_type: ItemType) -> TypeCategory:
    """What an item type holds: from Jama's category, then its type key, then its name.

    Args:
        item_type (ItemType): The item type.

    Returns:
        TypeCategory: The category, ``OTHER`` when none of the three says.
    """
    if item_type.category and (found := _CATEGORY_TOKENS.get(_token(item_type.category))):
        return found
    if found := _TYPE_KEYS.get(_token(item_type.type_key)):
        return found
    if _REQUIREMENT_NAME.search(item_type.display.strip()):
        return TypeCategory.REQUIREMENT
    return TypeCategory.OTHER


@dataclass(frozen=True)
class DiscoveredType:
    """An item type a project uses.

    Attributes:
        item_type (ItemType): The type.
        category (TypeCategory): What it holds.
        count (int | None): How many items of it the project has, or None for containers and
            when Jama didn't say.
    """

    item_type: ItemType
    category: TypeCategory
    count: int | None


@dataclass(frozen=True)
class Discovery:
    """A project and the item types it uses.

    Attributes:
        project (Project): The project.
        item_types (tuple[DiscoveredType, ...]): The item types it uses.
    """

    project: Project
    item_types: tuple[DiscoveredType, ...]

    def requirement_types(self) -> tuple[str, ...]:
        """The ids of the requirement types the project has items of.

        Returns:
            tuple[str, ...]: The item type ids.
        """
        return self._with_items(TypeCategory.REQUIREMENT)

    def test_case_types(self) -> tuple[str, ...]:
        """The ids of the test case types the project has items of.

        Returns:
            tuple[str, ...]: The item type ids.
        """
        return self._with_items(TypeCategory.TEST_CASE)

    def _with_items(self, category: TypeCategory) -> tuple[str, ...]:
        return tuple(t.item_type.id for t in self.item_types if t.category is category and t.count != 0)


def discover(client: JamaClient, project: str) -> Discovery:
    """Read a project's item types, with item counts.

    Args:
        client (JamaClient): The Jama client.
        project (str): The project id.

    Returns:
        Discovery: What the project has.
    """
    found = client.project(project)
    types = []
    for item_type in client.item_types(project):
        category = type_category(item_type)
        count = None if category is TypeCategory.CONTAINER else client.count_items(project, item_type.id)
        types.append(DiscoveredType(item_type, category, count))
    return Discovery(found, tuple(types))
