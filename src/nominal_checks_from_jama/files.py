"""The files the steps pass between them: ``requirements.json`` and ``checks.json``.

Each is JSON, indented, with its text written as is rather than as escape codes, so a person can
read it and a script can change it. JSON escapes every quote, backslash and line break inside a
string, so no requirement text can break the file. Each file names its kind and version, so a step
refuses a file it can't read rather than misreading it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

FORMAT_PREFIX = "nominal-checks-from-jama/"


class FileFormatError(ValueError):
    """A file isn't the kind or version a step reads."""


def write(path: str | Path, kind: str, version: int, body: Mapping[str, Any]) -> Path:
    """Write one of the tool's files.

    Args:
        path (str | Path): The file.
        kind (str): What it holds, such as ``requirements``.
        version (int): The version of that kind's layout.
        body (Mapping[str, Any]): Its contents, besides the kind and version.

    Returns:
        Path: The file written.
    """
    target = Path(path)
    data = {"format": FORMAT_PREFIX + kind, "version": version, **body}
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return target


def read(path: str | Path, kind: str, version: int) -> dict[str, Any]:
    """Read one of the tool's files, checking its kind and version.

    Args:
        path (str | Path): The file.
        kind (str): The kind expected.
        version (int): The version expected.

    Returns:
        dict[str, Any]: Its contents.

    Raises:
        FileFormatError: When it isn't JSON, or is another kind or version.
    """
    file = Path(path)
    try:
        loaded = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise FileFormatError(f"{file} isn't valid JSON: {error}") from None
    data: dict[str, Any] = loaded if isinstance(loaded, dict) else {}
    found = data.get("format")
    if found != FORMAT_PREFIX + kind:
        raise FileFormatError(f"{file} isn't a {kind} file: its format is {found!r}.")
    if data.get("version") != version:
        raise FileFormatError(
            f"{file} is version {data.get('version')!r} of the {kind} file; this tool reads {version}."
        )
    return data


def kind_of(path: str | Path) -> str | None:
    """The kind of one of the tool's files, such as ``checks``, without checking the rest.

    Args:
        path (str | Path): The file.

    Returns:
        str | None: The kind, or None when it isn't one of the tool's files.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    found = data.get("format") if isinstance(data, dict) else None
    if isinstance(found, str) and found.startswith(FORMAT_PREFIX):
        return found.removeprefix(FORMAT_PREFIX)
    return None
