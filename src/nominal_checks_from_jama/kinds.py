"""Which Jama items a run works on: requirements, or test cases.

Each kind has its own item types in the settings, its own files and its own checklist in Nominal,
so the people who keep requirement checks and those who keep test checks don't share a checklist.
"""

from __future__ import annotations

from enum import StrEnum


class ItemKind(StrEnum):
    """Which Jama items a run works on."""

    REQUIREMENTS = "requirements"
    """Items of the types in ``[jama] item_types``."""
    TEST_CASES = "test_cases"
    """Items of the types in ``[jama] test_case_types``."""

    @property
    def plural(self) -> str:
        """The items' name in sentences, such as ``"test cases"``."""
        return "requirements" if self is ItemKind.REQUIREMENTS else "test cases"

    @property
    def singular(self) -> str:
        """One item's name in sentences, such as ``"test case"``."""
        return "requirement" if self is ItemKind.REQUIREMENTS else "test case"

    def counted(self, number: int) -> str:
        """A number of items, such as ``"1 test case"`` or ``"3 requirements"``."""
        return f"{number} {self.singular if number == 1 else self.plural}"

    @property
    def types_setting(self) -> str:
        """The ``[jama]`` setting that lists this kind's item types."""
        return "item_types" if self is ItemKind.REQUIREMENTS else "test_case_types"

    @property
    def items_file(self) -> str:
        """The default file for step 1."""
        return "requirements.json" if self is ItemKind.REQUIREMENTS else "test-cases.json"

    @property
    def checks_file(self) -> str:
        """The default file for step 2."""
        return "checks.json" if self is ItemKind.REQUIREMENTS else "test-checks.json"

    @property
    def plan_file(self) -> str:
        """The default file for the agent plan."""
        return "checks-plan.md" if self is ItemKind.REQUIREMENTS else "test-checks-plan.md"
