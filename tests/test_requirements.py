"""Step 1: reading the requirements from Jama, and their file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import respx

from nominal_checks_from_jama._jama import JamaClient
from nominal_checks_from_jama.config import Config, JamaSettings
from nominal_checks_from_jama.files import FileFormatError
from nominal_checks_from_jama.kinds import ItemKind
from nominal_checks_from_jama.requirements import ReadError, Requirements, Source, read_requirements

from .conftest import BASE
from .fake_jama import FakeJama


@pytest.fixture
def project(api: respx.MockRouter) -> FakeJama:
    fake = FakeJama()
    fake.install(api)
    return fake


def settings(*item_types: str) -> Config:
    return Config(jama=JamaSettings(base_url=BASE, project="12", item_types=item_types))


def test_reads_the_requirement_types(jama: JamaClient, project: FakeJama) -> None:
    read = read_requirements(settings("34"), jama=jama)
    assert read.source == Source(BASE, "12", "Widget Assembly")
    assert [(r.document_key, r.name) for r in read.requirements] == [
        ("WA-REQ-101", "Brake temperature"),
        ("WA-REQ-102", "Pedal force"),
    ]
    first = read.requirements[0]
    assert first.text == "Stays below 450°C during a hot stop."
    assert first.html == "<p>Stays below 450&deg;C during a hot stop.</p>"
    assert first.url == f"{BASE}/perspective.req#/items/101?projectId=12"


def test_a_listing_that_stopped_early_stops_the_read(jama: JamaClient, project: FakeJama) -> None:
    project.truncate_type = 34
    with pytest.raises(ReadError, match="stopped early"):
        read_requirements(settings("34"), jama=jama)


def test_no_item_types_stops_the_read(jama: JamaClient, project: FakeJama) -> None:
    with pytest.raises(ReadError, match="item_types is empty"):
        read_requirements(settings(), jama=jama)


def test_reads_test_cases_with_their_steps(tmp_path: Path, jama: JamaClient, project: FakeJama) -> None:
    project.set_field(
        201,
        "testCaseSteps",
        [
            {"action": "Heat the rotor to 300 C.", "expectedResult": "`brake_temp` reads 300 &plusmn; 5.", "notes": ""},
            {"action": "Release the brake.", "expectedResult": "Temp < 450 C."},
        ],
    )
    config = Config(jama=JamaSettings(base_url=BASE, project="12", test_case_types=("35",)))
    read = read_requirements(config, jama=jama, kind=ItemKind.TEST_CASES)
    assert read.kind is ItemKind.TEST_CASES
    (test_case,) = read.requirements
    assert test_case.text == (
        "Steps.\n\nSteps:\n"
        "1. Action: Heat the rotor to 300 C.\n   Expected result: `brake_temp` reads 300 &plusmn; 5.\n"
        "2. Action: Release the brake.\n   Expected result: Temp < 450 C."
    )
    # plain-text steps are escaped into the HTML, so "<" stays text
    assert "<p>Expected result: Temp &lt; 450 C.</p>" in test_case.html
    path = read.save(tmp_path / ItemKind.TEST_CASES.items_file)
    assert Requirements.load(path) == read


def test_no_test_case_types_stops_the_read(jama: JamaClient, project: FakeJama) -> None:
    with pytest.raises(ReadError, match="test_case_types is empty"):
        read_requirements(settings("34"), jama=jama, kind=ItemKind.TEST_CASES)


def test_requirements_survive_a_round_trip_through_their_file(
    tmp_path: Path, jama: JamaClient, project: FakeJama
) -> None:
    read = read_requirements(settings("34"), jama=jama)
    path = read.save(tmp_path / "requirements.json")
    assert Requirements.load(path) == read
    data = json.loads(path.read_text(encoding="utf-8"))
    assert (data["format"], data["version"]) == ("nominal-checks-from-jama/requirements", 1)


def test_a_newer_file_version_is_refused(tmp_path: Path) -> None:
    path = Requirements(Source(BASE, "12", "W"), ()).save(tmp_path / "requirements.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps({**data, "version": 2}), encoding="utf-8")
    with pytest.raises(FileFormatError, match="version 2"):
        Requirements.load(path)


def test_a_file_that_isnt_json_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "requirements.json"
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(FileFormatError, match="isn't valid JSON"):
        Requirements.load(path)
