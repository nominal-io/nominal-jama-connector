"""Check the Jama reader against a real Jama Connect project.

CI doesn't run this; the unit tests mock Jama. Run it with ``just test-live`` against a project
you can use for testing. It only reads, and prints counts and truncation flags, never item content.

Settings come from the environment, so credentials stay out of shell history and arguments:

- ``JAMA_BASE_URL``: the instance's address.
- ``JAMA_PROJECT_ID``: the project to check.
- ``JAMA_CLIENT_ID`` and ``JAMA_CLIENT_SECRET``: an API client. Or ``JAMA_ACCESS_TOKEN``.

Scopes, each including the ones before it:

- ``connection``: sign in and read the current user.
- ``project``: read the project and its item types with fields.
- ``items``: read up to ``--max-items`` items of each type.

Exit codes: 0 when every check passed, 1 when one failed, 2 for missing settings.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable
from typing import TypeVar

from nominal_checks_from_jama._jama import ItemType, JamaClient, JamaHTTPError, ListResult

SCOPES = ("connection", "project", "items")
T = TypeVar("T")


def _client() -> JamaClient | None:
    base_url = os.environ.get("JAMA_BASE_URL", "")
    client_id = os.environ.get("JAMA_CLIENT_ID", "")
    client_secret = os.environ.get("JAMA_CLIENT_SECRET", "")
    token = os.environ.get("JAMA_ACCESS_TOKEN", "")
    if base_url and client_id and client_secret:
        return JamaClient.from_client_credentials(base_url, client_id, client_secret)
    if base_url and token:
        return JamaClient.from_token(base_url, token)
    return None


def _listing(name: str, result: ListResult[T]) -> str:
    total = "?" if result.total is None else str(result.total)
    flags = (" truncated" if result.truncated else "") + (f" dropped={result.dropped}" if result.dropped else "")
    return f"{name}: {len(result)} of {total}{flags}"


def _check(label: str, run: Callable[[], str]) -> bool:
    try:
        print(f"ok    {label}: {run()}")
        return True
    except JamaHTTPError as error:
        print(f"FAIL  {label}: {error}")
        return False


def main(argv: list[str] | None = None) -> int:
    """Run the checks.

    Args:
        argv (list[str] | None): Command-line arguments; ``sys.argv`` when None.

    Returns:
        int: The exit code.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scope", choices=SCOPES, default="project")
    parser.add_argument("--max-items", type=int, default=100, help="items to read per type (items scope)")
    args = parser.parse_args(argv)

    project_id = os.environ.get("JAMA_PROJECT_ID", "")
    client = _client()
    if client is None or (args.scope != "connection" and not project_id):
        print(__doc__, file=sys.stderr)
        return 2

    level = SCOPES.index(args.scope)
    passed = True
    types: list[ItemType] = []

    def read_types() -> str:
        result = client.item_types(project_id)
        types.extend(result)
        return _listing("types", result)

    with client:
        passed &= _check("current user", lambda: "read" if client.current_user() else "no id in reply")
        if level >= 1:
            passed &= _check("project", lambda: f"key {client.project(project_id).project_key}")
            passed &= _check("item types", read_types)
            for item_type in types:
                passed &= _check(
                    f"item type {item_type.id}",
                    lambda t=item_type: f"{len(client.item_type(t.id).fields)} fields",  # type: ignore[misc]
                )
        if level >= 2:
            for item_type in types:
                passed &= _check(
                    f"items of type {item_type.id}",
                    lambda t=item_type: _listing(  # type: ignore[misc]
                        "items", client.items(project_id, t.id, max_rows=args.max_items)
                    ),
                )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
