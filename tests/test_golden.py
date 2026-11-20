"""Each step's file for the invented project, against a copy kept in tests/golden/.

A change to what a step writes fails here, so a change to one step can't quietly change what the
next one reads. When the change is intended, regenerate the copies with
``UPDATE_GOLDEN=1 just test tests/test_golden.py`` and review the diff.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import respx

from nominal_checks_from_jama._jama import JamaClient
from nominal_checks_from_jama.agent_plan import write_agent_plan
from nominal_checks_from_jama.checks import build_checks
from nominal_checks_from_jama.config import Config, JamaSettings
from nominal_checks_from_jama.requirements import read_requirements

from .conftest import BASE
from .fake_jama import FakeJama

GOLDEN = Path(__file__).parent / "golden"


@pytest.fixture
def project(api: respx.MockRouter) -> FakeJama:
    fake = FakeJama()
    fake.set_field(101, "description", '<p>`brake_temp` stays below 450&deg;C during a "hot stop"; no fade.</p>')
    fake.install(api)
    return fake


def test_each_steps_file_matches_its_golden_copy(tmp_path: Path, jama: JamaClient, project: FakeJama) -> None:
    config = Config(jama=JamaSettings(base_url=BASE, project="12", item_types=("34",)))
    requirements = read_requirements(config, jama=jama)
    checks = build_checks(requirements)
    outputs = {
        "requirements.json": requirements.save(tmp_path / "requirements.json").read_text(encoding="utf-8"),
        "checks.json": checks.save(tmp_path / "checks.json").read_text(encoding="utf-8"),
        "checks-plan.md": write_agent_plan(checks, target="ri.scout.example.run.1").markdown,
    }
    for name, text in outputs.items():
        golden = GOLDEN / name
        if os.environ.get("UPDATE_GOLDEN"):
            golden.write_text(text, encoding="utf-8", newline="\n")
        assert golden.read_text(encoding="utf-8") == text, (
            f"{name} changed. If that's intended, see this module's docstring."
        )
