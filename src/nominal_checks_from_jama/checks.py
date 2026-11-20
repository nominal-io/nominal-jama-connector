"""Step 2: turn requirements or test cases into the checks to keep. Its file is ``checks.json``,
or ``test-checks.json`` for test cases.

Nothing here calls Jama or Nominal. A check's title is the item's document key and name, and its
description is the item's text, then a line linking back to Jama. That line is how both outputs,
the Nominal checklist and an agent's, find an item's check again later.

To change how checks are made, pass your own :data:`~nominal_checks_from_jama.markers.ChannelFinder`
to :func:`build_checks`, or write ``checks.json`` with your own code: both outputs read only that.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from nominal_checks_from_jama import files
from nominal_checks_from_jama.kinds import ItemKind
from nominal_checks_from_jama.markers import ChannelFinder, marked_channels
from nominal_checks_from_jama.requirements import Requirements, Source

KIND = "checks"
VERSION = 1

JAMA_LINK = "Jama: "
"""Starts the line in a check's description that links to its requirement."""

# Permanent: changing it would change every lineage, and checks made before would no longer match.
_LINEAGE_NAMESPACE = uuid.UUID("6f3c2d4e-8a1b-4c7d-9e2f-3a5b7c9d1e0f")

_LINK_LINE = re.compile(r"^" + re.escape(JAMA_LINK) + r"(\S+)\s*$", re.MULTILINE)
_ITEM_URL = re.compile(r"/perspective\.req#/items/(\d+)\?projectId=(\d+)$")


@dataclass(frozen=True)
class CheckSpec:
    """One check to keep, for one requirement.

    Attributes:
        item_id (str): The requirement's Jama item id.
        document_key (str): Its document key.
        url (str): Its URL in Jama.
        lineage (str): The check's lineage in Nominal: a UUID made from the Jama URL and item id,
            the same on every run.
        title (str): The check's title.
        description (str): The check's description, ending with the line linking to Jama.
        channels (tuple[str, ...]): The channel names to make checklist variables for.
    """

    item_id: str
    document_key: str
    url: str
    lineage: str
    title: str
    description: str
    channels: tuple[str, ...] = ()


@dataclass(frozen=True)
class Checks:
    """Every check to keep for one Jama project's requirements, or for its test cases.

    Attributes:
        source (Source): The Jama project.
        checks (tuple[CheckSpec, ...]): The checks, ordered by document key.
        kind (ItemKind): Whether the checks are for requirements or test cases. Each kind has its
            own checklist.
    """

    source: Source
    checks: tuple[CheckSpec, ...]
    kind: ItemKind = ItemKind.REQUIREMENTS

    def save(self, path: str | Path | None = None) -> Path:
        """Write the checks to a file.

        Args:
            path (str | Path | None): The file; ``checks.json`` or ``test-checks.json`` when None.

        Returns:
            Path: The file written.
        """
        return files.write(
            path if path is not None else self.kind.checks_file,
            KIND,
            VERSION,
            {
                "items": str(self.kind),
                "source": vars(self.source),
                "checks": [{**vars(check), "channels": list(check.channels)} for check in self.checks],
            },
        )

    @classmethod
    def load(cls, path: str | Path = "checks.json") -> Checks:
        """Read checks from a file :meth:`save` wrote, or that your own code wrote in the same layout.

        Args:
            path (str | Path): The file.

        Returns:
            Checks: The checks.

        Raises:
            FileFormatError: When the file isn't a checks file this version reads.
        """
        data = files.read(path, KIND, VERSION)
        try:
            return cls(
                source=Source(**data["source"]),
                checks=tuple(
                    CheckSpec(**{**entry, "channels": tuple(entry.get("channels", ()))}) for entry in data["checks"]
                ),
                kind=ItemKind(data.get("items", ItemKind.REQUIREMENTS)),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise files.FileFormatError(f"{path} is missing or has an unknown field: {error}") from None


def lineage(base_url: str, item_id: str) -> str:
    """The check lineage for a requirement: the same on every run, and when the requirement is renamed.

    Args:
        base_url (str): The Jama instance's URL.
        item_id (str): The Jama item id.

    Returns:
        str: The lineage, a UUID.
    """
    return str(uuid.uuid5(_LINEAGE_NAMESPACE, f"{base_url.rstrip('/').lower()}/{item_id}"))


def linked_item(description: str, source: Source) -> str | None:
    """The Jama item a check's description links to, when it's in ``source``'s project.

    Args:
        description (str): The check's description.
        source (Source): The Jama project.

    Returns:
        str | None: The item id, or None when the description has no link to an item in the project.
    """
    base = source.base_url.rstrip("/").lower()
    for match in _LINK_LINE.finditer(description):
        url = match.group(1)
        found = _ITEM_URL.search(url)
        if found and url.lower().startswith(base) and found.group(2) == source.project:
            return found.group(1)
    return None


def split_notes(description: str, url: str) -> tuple[str, str]:
    """A check's description split at its line linking to ``url``: Jama's text, and the notes after it.

    Jama is the source of truth for the text up to and including the link line. What follows it is
    notes, from the user or an agent, which a sync keeps.

    Args:
        description (str): The check's description.
        url (str): The URL of the check's item in Jama.

    Returns:
        tuple[str, str]: The description up to and including the link line, and the notes after it,
        without surrounding blank lines. The whole description and no notes when it has no such line.
    """
    link = JAMA_LINK + url
    lines = description.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == link:
            return "\n".join(lines[: index + 1]), "\n".join(lines[index + 1 :]).strip()
    return description, ""


def build_checks(
    requirements: Requirements,
    find_channels: ChannelFinder | None = None,
    *,
    markers: tuple[str, ...] = (),
) -> Checks:
    """Make a check for each requirement.

    Args:
        requirements (Requirements): The requirements, from step 1.
        find_channels (ChannelFinder | None): Finds the channel names in a requirement. When None,
            the tool's own: names marked with backticks, code formatting and ``markers``.
        markers (tuple[str, ...]): The extra marker pairs the tool's own finder uses, from
            :data:`~nominal_checks_from_jama.markers.PAIRS`. Ignored when ``find_channels`` is given.

    Returns:
        Checks: The checks, ordered by document key.
    """
    finder = find_channels or marked_channels(markers)
    base_url = requirements.source.base_url
    checks = [
        CheckSpec(
            item_id=requirement.item_id,
            document_key=requirement.document_key,
            url=requirement.url,
            lineage=lineage(base_url, requirement.item_id),
            title=f"{requirement.document_key} {requirement.name}".strip(),
            description=_description(requirement.text, requirement.url),
            channels=tuple(dict.fromkeys(finder(requirement))),
        )
        for requirement in requirements.requirements
    ]
    ordered = tuple(sorted(checks, key=lambda check: natural(check.document_key)))
    return Checks(requirements.source, ordered, requirements.kind)


def _description(text: str, url: str) -> str:
    link = JAMA_LINK + url
    return f"{text}\n\n{link}" if text else link


def natural(key: str) -> tuple[object, ...]:
    """A sort key that puts ``WA-REQ-9`` before ``WA-REQ-10``.

    Args:
        key (str): A document key.

    Returns:
        tuple[object, ...]: The sort key.
    """
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", key))
