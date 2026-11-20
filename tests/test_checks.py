"""Step 2: requirements into checks. Nothing here calls Jama or Nominal."""

from __future__ import annotations

from pathlib import Path

import pytest

from nominal_checks_from_jama.checks import JAMA_LINK, Checks, build_checks, lineage, linked_item
from nominal_checks_from_jama.files import FileFormatError
from nominal_checks_from_jama.requirements import Requirement, Requirements, Source

from .conftest import BASE

SOURCE = Source(BASE, "12", "Widget Assembly")


def url(item_id: str, project: str = "12") -> str:
    return f"{BASE}/perspective.req#/items/{item_id}?projectId={project}"


def requirement(item_id: str, name: str, text: str = "", html: str = "") -> Requirement:
    return Requirement(item_id, f"WA-REQ-{item_id}", name, text, html or f"<p>{text}</p>", url(item_id))


def test_a_check_has_the_key_name_text_and_a_link_to_jama() -> None:
    checks = build_checks(Requirements(SOURCE, (requirement("101", "Brake temperature", "Stays below 450°C."),)))
    (check,) = checks.checks
    assert check.title == "WA-REQ-101 Brake temperature"
    assert check.description == f"Stays below 450°C.\n\n{JAMA_LINK}{url('101')}"
    assert check.lineage == lineage(BASE, "101")
    assert checks.source == SOURCE


def test_a_requirement_without_text_gets_only_the_link() -> None:
    (check,) = build_checks(Requirements(SOURCE, (requirement("7", "Empty"),))).checks
    assert check.description == JAMA_LINK + url("7")


def test_lineage_is_the_same_on_every_run_and_ignores_the_address_case() -> None:
    assert lineage(BASE, "101") == lineage(BASE.upper() + "/", "101")
    assert lineage(BASE, "101") != lineage(BASE, "102")


def test_checks_are_in_document_key_order() -> None:
    read = Requirements(SOURCE, tuple(requirement(i, f"R{i}") for i in ("10", "9", "100")))
    assert [c.document_key for c in build_checks(read).checks] == ["WA-REQ-9", "WA-REQ-10", "WA-REQ-100"]


def test_backticks_always_mark_channels_and_other_pairs_when_on() -> None:
    read = Requirements(SOURCE, (requirement("1", "R", "Keep `voltage` and {current} below [limit]."),))
    assert build_checks(read).checks[0].channels == ("voltage",)
    assert build_checks(read, markers=("{}",)).checks[0].channels == ("voltage", "current")


def test_code_formatting_marks_a_channel() -> None:
    read = Requirements(
        SOURCE, (requirement("1", "R", "Keep pressure low.", html="<p>Keep <code>pressure</code> low.</p>"),)
    )
    assert build_checks(read).checks[0].channels == ("pressure",)


def test_your_own_channel_finder_replaces_the_tools() -> None:
    read = Requirements(SOURCE, (requirement("1", "R", "CHANNEL: engine.rpm"),))
    checks = build_checks(read, lambda r: [line.split(": ", 1)[1] for line in r.text.splitlines()])
    assert checks.checks[0].channels == ("engine.rpm",)


def test_linked_item_finds_the_requirement_a_description_links_to() -> None:
    assert linked_item(f"Text.\n\n{JAMA_LINK}{url('101')}", SOURCE) == "101"
    assert linked_item(f"{JAMA_LINK}{BASE.upper()}/perspective.req#/items/101?projectId=12", SOURCE) == "101"


@pytest.mark.parametrize(
    "description",
    [
        "No link at all.",
        f"{JAMA_LINK}{url('101', project='13')}",  # another project
        f"{JAMA_LINK}https://other.jamacloud.com/perspective.req#/items/101?projectId=12",  # another instance
        f"See {JAMA_LINK}{url('101')} inline",  # not a line of its own
    ],
)
def test_linked_item_ignores_other_links(description: str) -> None:
    assert linked_item(description, SOURCE) is None


def test_checks_survive_a_round_trip_through_their_file(tmp_path: Path) -> None:
    text = 'Quote " semicolon ; backslash \\ brace } backtick ` line\nbreak, tab\t, emoji 🔥, ``` fence'
    checks = build_checks(Requirements(SOURCE, (requirement("1", 'Name "quoted"', text + " `volt`"),)))
    path = checks.save(tmp_path / "checks.json")
    assert Checks.load(path) == checks
    assert "🔥" in path.read_text(encoding="utf-8")  # written as is, not escaped


def test_loading_another_kind_of_file_fails(tmp_path: Path) -> None:
    path = Requirements(SOURCE, ()).save(tmp_path / "requirements.json")
    with pytest.raises(FileFormatError, match="isn't a checks file"):
        Checks.load(path)
