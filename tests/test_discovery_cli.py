from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from nominal_checks_from_jama._jama import ItemType, Project
from nominal_checks_from_jama.cli import _summary, main
from nominal_checks_from_jama.config import Config, JamaSettings, NominalSettings
from nominal_checks_from_jama.discovery import DiscoveredType, Discovery, TypeCategory, type_category

from .conftest import BASE, MemoryKeyring
from .fake_jama import FakeJama


@pytest.mark.parametrize(
    ("category", "key", "display", "expected"),
    [
        ("REQUIREMENTS", "SYS", "System Spec", TypeCategory.REQUIREMENT),
        (None, "REQ", "Anything", TypeCategory.REQUIREMENT),
        (None, "SR", "System Requirement", TypeCategory.REQUIREMENT),
        (None, "RS", "Requirement Set", TypeCategory.OTHER),
        ("FOLDER", "FLD", "Folder", TypeCategory.CONTAINER),
        (None, "TC", "Test Case", TypeCategory.OTHER),
        ("TEST_CASE", "TST", "Verification Test", TypeCategory.TEST_CASE),
    ],
)
def test_type_category(category: str | None, key: str, display: str, expected: TypeCategory) -> None:
    item_type = ItemType(id="1", type_key=key, display=display, display_plural=display, category=category)
    assert type_category(item_type) is expected


def test_summary_groups_the_types_it_doesnt_read_by_reason() -> None:
    def found(type_id: str, display: str, category: TypeCategory, count: int | None) -> DiscoveredType:
        item_type = ItemType(id=type_id, type_key="", display=display, display_plural=display, category=None)
        return DiscoveredType(item_type, category, count)

    discovery = Discovery(
        Project(id="60", name="Demo", project_key=None),
        (
            found("30", "Component", TypeCategory.CONTAINER, None),
            found("32", "Folder", TypeCategory.CONTAINER, None),
            found("27", "Defect", TypeCategory.OTHER, 0),
            found("45", "Stakeholder Requirement", TypeCategory.REQUIREMENT, 0),
            found("118", "System Requirement", TypeCategory.REQUIREMENT, 23),
            found("121", "Subsystem Requirement", TypeCategory.REQUIREMENT, 26),
            found("125", "Risk", TypeCategory.OTHER, 3),
            found("142", "Test Case", TypeCategory.TEST_CASE, 114),
        ),
    )
    assert _summary(discovery) == [
        "Project 60: Demo",
        "Reading 2 requirement types, 49 items, for the requirements checklist:",
        "  118 System Requirement (23 items)",
        "  121 Subsystem Requirement (26 items)",
        "Reading 1 test case type, 114 items, for a separate test cases checklist:",
        "  142 Test Case (114 items)",
        "Not reading:",
        "  125 Risk (3 items): not a requirement or test case type",
        "  2 types with no items in this project",
        "  2 container types, which hold other items: Component, Folder",
    ]


def test_init_writes_settings_and_keeps_the_secret_out(
    tmp_path: Path, memory_keyring: MemoryKeyring, fake: FakeJama
) -> None:
    config_path = tmp_path / "jama-checks.toml"
    result = CliRunner().invoke(
        main,
        ["--config", str(config_path), "init", "--base-url", BASE, "--project", "12", "--account", "client-a"],
        input="secret-b\n",
    )
    assert result.exit_code == 0, result.output
    assert "Stored the secret in your operating system's credential manager." in result.output
    assert f"Connecting to {BASE} to read project 12's item types..." in result.output
    assert "Reading 1 requirement type, 2 items, for the requirements checklist:\n  34 Requirement (2 items)\n" in (
        result.output
    )
    assert "Reading 1 test case type, 1 item, for a separate test cases checklist:\n  35 Test Case (1 item)\n" in (
        result.output
    )
    assert "Not reading:\n  1 container type, which holds other items: Folder\n" in result.output
    assert memory_keyring.secrets == {(f"nominal-checks-from-jama:{BASE}", "client-a"): "secret-b"}
    assert "secret-b" not in config_path.read_text(encoding="utf-8")
    jama = Config.load(config_path).jama
    assert (jama.item_types, jama.test_case_types) == (("34",), ("35",))


def test_init_takes_the_url_and_project_from_a_pasted_page(
    tmp_path: Path, memory_keyring: MemoryKeyring, fake: FakeJama
) -> None:
    config_path = tmp_path / "jama-checks.toml"
    page = f"{BASE}/perspective.req#/items/56?projectId=12"
    # the URL and the account are typed; Enter accepts the project id read from the URL
    result = CliRunner().invoke(main, ["--config", str(config_path), "init"], input=f"{page}\n\nclient-a\nsecret-b\n")
    assert result.exit_code == 0, result.output
    assert "Jama project id [12]" in result.output
    jama = Config.load(config_path).jama
    assert (jama.base_url, jama.project) == (BASE, "12")
    assert (f"nominal-checks-from-jama:{BASE}", "client-a") in memory_keyring.secrets


def test_init_asks_again_for_a_url_that_isnt_one(tmp_path: Path, memory_keyring: MemoryKeyring, fake: FakeJama) -> None:
    config_path = tmp_path / "jama-checks.toml"
    result = CliRunner().invoke(
        main, ["--config", str(config_path), "init"], input=f"ftp://nope\n{BASE}\n12\nclient-a\nsecret-b\n"
    )
    assert result.exit_code == 0, result.output
    assert "Not a Jama Connect URL" in result.output


def test_init_force_offers_the_settings_it_replaces(
    tmp_path: Path, memory_keyring: MemoryKeyring, fake: FakeJama
) -> None:
    config_path = Config(
        jama=JamaSettings(base_url=BASE, project="12", account="client-a"),
        nominal=NominalSettings(profile="staging", channel_markers=("{}",)),
    ).save(tmp_path / "jama-checks.toml")
    memory_keyring.secrets[(f"nominal-checks-from-jama:{BASE}", "client-a")] = "secret-b"
    # Enter at each prompt keeps the file's value
    result = CliRunner().invoke(main, ["--config", str(config_path), "init", "--force"], input="\n\n\n")
    assert result.exit_code == 0, result.output
    assert f"Jama Connect URL (paste it from your browser) [{BASE}]" in result.output
    assert "Jama project id [12]" in result.output
    assert "API client ID, or username [client-a]" in result.output
    replaced = Config.load(config_path)
    assert (replaced.jama.project, replaced.jama.account) == ("12", "client-a")
    assert replaced.nominal.profile == "staging"
    assert replaced.nominal.channel_markers == ("{}",)


def test_init_re_init_reads_the_types_again_without_asking(
    tmp_path: Path, memory_keyring: MemoryKeyring, fake: FakeJama
) -> None:
    config_path = Config(
        jama=JamaSettings(base_url=BASE, project="12", item_types=("99",), account="client-a"),
        nominal=NominalSettings(profile="staging"),
    ).save(tmp_path / "jama-checks.toml")
    memory_keyring.secrets[(f"nominal-checks-from-jama:{BASE}", "client-a")] = "secret-b"
    result = CliRunner().invoke(main, ["--config", str(config_path), "init", "--re-init"])
    assert result.exit_code == 0, result.output
    assert "Jama Connect URL" not in result.output
    replaced = Config.load(config_path)
    assert (replaced.jama.item_types, replaced.jama.test_case_types) == (("34",), ("35",))
    assert replaced.nominal.profile == "staging"


def test_init_re_init_needs_a_settings_file(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["--config", str(tmp_path / "none.toml"), "init", "--re-init"])
    assert result.exit_code == 1
    assert "Run `init` without --re-init" in result.output


def test_init_refuses_to_replace_without_force(tmp_path: Path) -> None:
    config_path = Config(jama=JamaSettings(base_url=BASE, project="12")).save(tmp_path / "jama-checks.toml")
    result = CliRunner().invoke(
        main, ["--config", str(config_path), "init", "--base-url", BASE, "--project", "12", "--account", "a"]
    )
    assert result.exit_code == 1
    assert "--force" in result.output


def test_login_stores_the_secret(tmp_path: Path, memory_keyring: MemoryKeyring) -> None:
    config_path = Config(jama=JamaSettings(base_url=BASE, project="12", account="client-a")).save(
        tmp_path / "jama-checks.toml"
    )
    result = CliRunner().invoke(main, ["--config", str(config_path), "login"], input="new-secret\n")
    assert result.exit_code == 0, result.output
    assert memory_keyring.secrets[(f"nominal-checks-from-jama:{BASE}", "client-a")] == "new-secret"


def test_missing_settings_file_explains(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["--config", str(tmp_path / "none.toml"), "login"])
    assert result.exit_code == 1
    assert "nominal-checks-from-jama init" in result.output


def test_hints_name_the_command_as_it_was_run(tmp_path: Path) -> None:
    missing = ["--config", str(tmp_path / "none.toml"), "login"]
    script = CliRunner().invoke(main, missing, prog_name="python nominal-checks-from-jama.py")
    assert "Run `python nominal-checks-from-jama.py init` to create one." in script.output
    config_path = Config(jama=JamaSettings(base_url=BASE, project="12", item_types=("34",), account="a")).save(
        tmp_path / "jama-checks.toml"
    )
    no_secret = CliRunner().invoke(
        main, ["--config", str(config_path), "read"], prog_name="python -m nominal_checks_from_jama"
    )
    assert "Run `python -m nominal_checks_from_jama login` to store it." in no_secret.output
