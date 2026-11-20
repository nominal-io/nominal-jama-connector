"""Step 1: read a Jama project's requirements or test cases. Its file is ``requirements.json``, or
``test-cases.json`` for test cases.

An item here is what Jama has, nothing more: deciding what a check holds is step 2, in
:mod:`nominal_checks_from_jama.checks`. The description is kept both as Jama's HTML and as plain
text, so the next step can look at either. A test case's steps follow its description.
"""

from __future__ import annotations

import html as html_module
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from nominal_checks_from_jama import files
from nominal_checks_from_jama._jama import Item, JamaClient, html_to_text
from nominal_checks_from_jama.config import DEFAULT_CONFIG, Config
from nominal_checks_from_jama.credentials import jama_client
from nominal_checks_from_jama.kinds import ItemKind

KIND = "requirements"
VERSION = 1

STEPS_FIELD = "testCaseSteps"
"""The Jama field that holds a test case's steps."""

# A step's fields as Jama's help names them: Action, Expected Result and Notes.
_STEP_FIELDS = (("action", "Action"), ("expectedResult", "Expected result"), ("notes", "Notes"))
_TAG = re.compile(r"<[a-zA-Z/][^>]*>")


class ReadError(Exception):
    """Reading the requirements stopped before it had all of them."""


@dataclass(frozen=True)
class Source:
    """The Jama project the requirements come from.

    Attributes:
        base_url (str): The Jama instance's URL.
        project (str): The project id.
        project_name (str): The project's name.
    """

    base_url: str
    project: str
    project_name: str


@dataclass(frozen=True)
class Requirement:
    """One Jama requirement or test case, as Jama has it.

    Attributes:
        item_id (str): The Jama item id.
        document_key (str): The item's document key, such as ``WA-REQ-12``, or its id when it has none.
        name (str): The item's name.
        text (str): The item's description as plain text, then a test case's steps.
        html (str): The item's description as Jama stores it, in HTML, then a test case's steps.
        url (str): The item's URL in Jama.
    """

    item_id: str
    document_key: str
    name: str
    text: str
    html: str
    url: str

    @classmethod
    def from_item(cls, item: Item, url: str) -> Requirement:
        """Read a requirement from a Jama item.

        Args:
            item (Item): The item.
            url (str): Its URL in Jama.

        Returns:
            Requirement: The requirement.
        """
        description = item.fields.get("description")
        html = description if isinstance(description, str) else ""
        text = html_to_text(html)
        steps_text, steps_html = _steps(item.fields.get(STEPS_FIELD))
        if steps_text:
            text = f"{text}\n\n{steps_text}" if text else steps_text
            html += steps_html
        return cls(
            item_id=item.id,
            document_key=item.document_key or item.id,
            name=(item.name or "").strip(),
            text=text,
            html=html,
            url=url,
        )


def _steps(value: object) -> tuple[str, str]:
    """A test case's steps as plain text and as HTML, or two empty strings when it has none.

    Steps are plain text unless the instance turns on rich text for them, so a value is escaped
    unless it holds tags.
    """
    if not isinstance(value, list):
        return "", ""
    labels = dict(_STEP_FIELDS)
    text: list[str] = []
    html: list[str] = []
    for step in value:
        if not isinstance(step, dict):
            continue
        # the known fields first, then any others, so nothing a step holds is dropped
        keys = [key for key in labels if key in step] + [key for key in step if key not in labels]
        parts = [
            (labels.get(key, key), raw if _TAG.search(raw) else html_module.escape(raw))
            for key in keys
            if isinstance(raw := step[key], str) and raw.strip()
        ]
        if not parts:
            continue
        lines = [f"{label}: {html_to_text(value)}".replace("\n", "\n   ") for label, value in parts]
        text.append(f"{len(text) + 1}. " + "\n   ".join(lines))
        html.append("<li>" + "".join(f"<p>{label}: {value}</p>" for label, value in parts) + "</li>")
    if not text:
        return "", ""
    return "Steps:\n" + "\n".join(text), "<p>Steps:</p><ol>" + "".join(html) + "</ol>"


@dataclass(frozen=True)
class Requirements:
    """Every requirement, or every test case, read from one Jama project.

    Attributes:
        source (Source): The project.
        requirements (tuple[Requirement, ...]): Its requirements or test cases.
        kind (ItemKind): Which of the two they are.
    """

    source: Source
    requirements: tuple[Requirement, ...]
    kind: ItemKind = ItemKind.REQUIREMENTS

    def save(self, path: str | Path | None = None) -> Path:
        """Write the items to a file.

        Args:
            path (str | Path | None): The file; ``requirements.json`` or ``test-cases.json`` when None.

        Returns:
            Path: The file written.
        """
        return files.write(
            path if path is not None else self.kind.items_file,
            KIND,
            VERSION,
            {
                "items": str(self.kind),
                "source": vars(self.source),
                "requirements": [vars(requirement) for requirement in self.requirements],
            },
        )

    @classmethod
    def load(cls, path: str | Path = "requirements.json") -> Requirements:
        """Read requirements or test cases from a file :meth:`save` wrote.

        Args:
            path (str | Path): The file.

        Returns:
            Requirements: The requirements or test cases.

        Raises:
            FileFormatError: When the file isn't a requirements file this version reads.
        """
        data = files.read(path, KIND, VERSION)
        try:
            return cls(
                source=Source(**data["source"]),
                requirements=tuple(Requirement(**entry) for entry in data["requirements"]),
                kind=ItemKind(data.get("items", ItemKind.REQUIREMENTS)),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise files.FileFormatError(f"{path} is missing or has an unknown field: {error}") from None


def read_requirements(
    config: Config | str | Path = DEFAULT_CONFIG,
    *,
    jama: JamaClient | None = None,
    kind: ItemKind = ItemKind.REQUIREMENTS,
) -> Requirements:
    """Read every requirement, or every test case, of the item types the settings list.

    Args:
        config (Config | str | Path): The settings, or the path of the settings file.
        jama (JamaClient | None): The Jama client; one signed in from the settings when None.
        kind (ItemKind): Requirements, from ``[jama] item_types``, or test cases, from
            ``[jama] test_case_types``.

    Returns:
        Requirements: The project and its requirements or test cases.

    Raises:
        ReadError: When no item types are listed, or Jama's listing stopped early. A partial list
            would make items look removed.
    """
    settings = config if isinstance(config, Config) else Config.load(config)
    client = jama or jama_client(settings.jama)
    try:
        return _read(client, settings, kind)
    finally:
        if jama is None:
            client.close()


def _read(client: JamaClient, settings: Config, kind: ItemKind) -> Requirements:
    jama = settings.jama
    types = jama.types(kind)
    if not types:
        raise ReadError(f"[jama] {kind.types_setting} is empty. List the item type ids that hold {kind.plural}.")
    project = client.project(jama.project)
    read: list[Requirement] = []
    for item_type in types:
        items = client.items(jama.project, item_type)
        if items.truncated:
            raise ReadError(
                f"Jama's listing of item type {item_type} stopped early, after {len(items)} items. "
                f"Nothing was written, so no {kind.singular} looks removed by mistake."
            )
        read.extend(_requirements(client, jama.project, items))
    return Requirements(Source(jama.base_url, jama.project, project.name), tuple(read), kind)


def _requirements(client: JamaClient, project: str, items: Iterable[Item]) -> list[Requirement]:
    return [Requirement.from_item(item, client.item_url(project, item.id)) for item in items]
