"""The Nominal output: keeping the checklist in line with the checks, with Jama as the source of truth."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import respx
from click.testing import CliRunner

from nominal_checks_from_jama import cli
from nominal_checks_from_jama._jama import JamaClient
from nominal_checks_from_jama._nominal import ChecklistConflict, ExistingCheck
from nominal_checks_from_jama.checks import JAMA_LINK, Checks, split_notes
from nominal_checks_from_jama.cli import main
from nominal_checks_from_jama.config import Config, JamaSettings, NominalSettings
from nominal_checks_from_jama.kinds import ItemKind
from nominal_checks_from_jama.nominal_sync import Field, Outcome, SyncError, SyncResult, sync
from nominal_checks_from_jama.pipeline import checks_from_jama

from .conftest import BASE
from .fake_jama import FakeJama
from .fake_nominal import FakeChecklists

PROPERTIES = {"jama_host": "example.jamacloud.com", "jama_project": "12", "jama_items": "requirements"}


@pytest.fixture
def project(api: respx.MockRouter) -> FakeJama:
    fake = FakeJama()
    fake.install(api)
    return fake


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(
        jama=JamaSettings(base_url=BASE, project="12", item_types=("34",)), path=tmp_path / "jama-checks.toml"
    )


def run(config: Config, jama: JamaClient, service: FakeChecklists, **kwargs: object) -> SyncResult:
    return sync(checks_from_jama(config, jama=jama), checklists=service, **kwargs)  # type: ignore[arg-type]


def outcomes(result: SyncResult) -> dict[str, Outcome]:
    return {r.title.split()[0]: r.outcome for r in result.plan.results}


def url(item_id: int) -> str:
    return f"{BASE}/perspective.req#/items/{item_id}?projectId=12"


def test_first_sync_creates_the_checklist(config: Config, jama: JamaClient, project: FakeJama) -> None:
    nominal = FakeChecklists()
    result = run(config, jama, nominal)
    assert result.created
    assert outcomes(result) == {"WA-REQ-101": Outcome.CREATED, "WA-REQ-102": Outcome.CREATED}
    checklist = nominal.only()
    assert checklist.name == "Widget Assembly requirements"
    assert checklist.properties == PROPERTIES
    assert [c.title for c in checklist.checks] == ["WA-REQ-101 Brake temperature", "WA-REQ-102 Pedal force"]
    assert checklist.checks[0].description == f"Stays below 450°C during a hot stop.\n\n{JAMA_LINK}{url(101)}"
    assert {c.priority for c in checklist.checks} == {"P3"}
    assert result.checklist_url == f"https://app.example.test/checklists/{result.checklist_rid}"


def test_a_second_sync_without_changes_commits_nothing(config: Config, jama: JamaClient, project: FakeJama) -> None:
    nominal = FakeChecklists(normalize=lambda text: text.replace("\n\n", " "))  # Nominal may store text differently
    run(config, jama, nominal)
    result = run(config, jama, nominal)
    assert not result.committed
    assert set(outcomes(result).values()) == {Outcome.UNCHANGED}
    assert nominal.commits == 0


def test_a_change_in_jama_rewrites_the_check_and_keeps_its_condition(
    config: Config, jama: JamaClient, project: FakeJama
) -> None:
    nominal = FakeChecklists()
    run(config, jama, nominal)
    nominal.edit("WA-REQ-101", has_condition=True)
    project.set_field(101, "description", "<p>Stays below 400&deg;C.</p>")
    result = run(config, jama, nominal)
    assert result.committed
    assert outcomes(result)["WA-REQ-101"] is Outcome.UPDATED
    (difference,) = result.plan.results[0].differences
    assert difference.field is Field.DESCRIPTION
    check = nominal.only().checks[0]
    assert check.description.startswith("Stays below 400°C.")
    assert check.has_condition


def test_notes_after_the_link_line_are_not_a_difference_and_survive_a_rewrite(
    config: Config, jama: JamaClient, project: FakeJama
) -> None:
    nominal = FakeChecklists()
    run(config, jama, nominal)
    notes = "Notes:\nThe state is taken as vertical speed within 0.5 m/s."
    original = nominal.only().checks[0].description
    nominal.edit("WA-REQ-101", description=f"{original}\n\n{notes}")
    assert outcomes(run(config, jama, nominal))["WA-REQ-101"] is Outcome.UNCHANGED
    project.set_field(101, "description", "<p>Stays below 400&deg;C.</p>")
    result = run(config, jama, nominal)
    assert outcomes(result)["WA-REQ-101"] is Outcome.UPDATED
    (difference,) = result.plan.results[0].differences
    assert notes not in difference.nominal  # the difference shows Jama's text only
    assert nominal.only().checks[0].description == f"Stays below 400°C.\n\n{JAMA_LINK}{url(101)}\n\n{notes}"


def test_split_notes_splits_at_the_items_own_link_line() -> None:
    link = f"{JAMA_LINK}{url(101)}"
    assert split_notes(f"Text.\n\n{link}\n\nNotes:\nA.", url(101)) == (f"Text.\n\n{link}", "Notes:\nA.")
    assert split_notes(f"Text.\n\n{link}", url(101)) == (f"Text.\n\n{link}", "")
    assert split_notes("Text without a link.", url(101)) == ("Text without a link.", "")


def test_an_edit_in_nominal_is_reported_and_rewritten_from_jama(
    config: Config, jama: JamaClient, project: FakeJama
) -> None:
    nominal = FakeChecklists()
    run(config, jama, nominal)
    nominal.edit("WA-REQ-102", title="WA-REQ-102 Pedal forse")
    result = run(config, jama, nominal)
    assert outcomes(result)["WA-REQ-102"] is Outcome.UPDATED
    (difference,) = result.plan.results[1].differences
    assert (difference.field, difference.nominal, difference.jama) == (
        Field.TITLE,
        "WA-REQ-102 Pedal forse",
        "WA-REQ-102 Pedal force",
    )
    assert nominal.only().checks[1].title == "WA-REQ-102 Pedal force"


def test_update_none_only_reports_differences(config: Config, jama: JamaClient, project: FakeJama) -> None:
    nominal = FakeChecklists()
    run(config, jama, nominal)
    nominal.edit("WA-REQ-102", title="WA-REQ-102 Pedal forse")
    result = run(config, jama, nominal, update=())
    assert outcomes(result)["WA-REQ-102"] is Outcome.DIFFERS
    assert not result.committed
    assert nominal.only().checks[1].title == "WA-REQ-102 Pedal forse"


def test_update_title_only_leaves_the_description(config: Config, jama: JamaClient, project: FakeJama) -> None:
    nominal = FakeChecklists()
    run(config, jama, nominal)
    nominal.edit("WA-REQ-102", title="Renamed", description="Edited text.")
    result = run(config, jama, nominal, update=(Field.TITLE,))
    assert outcomes(result)["WA-REQ-102"] is Outcome.UPDATED
    check = nominal.only().checks[1]
    assert (check.title, check.description) == ("WA-REQ-102 Pedal force", "Edited text.")


def test_a_check_the_tool_cant_copy_is_reported_not_rewritten(
    config: Config, jama: JamaClient, project: FakeJama
) -> None:
    nominal = FakeChecklists()
    run(config, jama, nominal)
    nominal.edit("WA-REQ-102", title="Renamed", copyable=False)
    result = run(config, jama, nominal)
    assert outcomes(result)["Renamed"] is Outcome.CANT_UPDATE
    assert not result.committed


def test_a_requirement_gone_from_jama_is_reported_and_removed_on_request(
    config: Config, jama: JamaClient, project: FakeJama
) -> None:
    nominal = FakeChecklists()
    run(config, jama, nominal)
    del project.items[102]
    kept = run(config, jama, nominal)
    assert outcomes(kept)["WA-REQ-102"] is Outcome.GONE
    assert not kept.committed
    removed = run(config, jama, nominal, remove_missing=True)
    assert outcomes(removed)["WA-REQ-102"] is Outcome.REMOVED
    assert [c.title for c in nominal.only().checks] == ["WA-REQ-101 Brake temperature"]


def test_a_check_deleted_in_nominal_is_made_again(config: Config, jama: JamaClient, project: FakeJama) -> None:
    nominal = FakeChecklists()
    run(config, jama, nominal)
    nominal.delete("WA-REQ-101")
    result = run(config, jama, nominal)
    assert outcomes(result)["WA-REQ-101"] is Outcome.CREATED
    assert len(nominal.only().checks) == 2


def test_checks_an_agent_made_are_found_by_their_link(config: Config, jama: JamaClient, project: FakeJama) -> None:
    nominal = FakeChecklists()
    agents = ExistingCheck(
        rid="ri.check.agent",
        lineage="00000000-0000-4000-8000-000000000001",
        title="WA-REQ-101 Brake temperature",
        description=f"Stays below 450°C during a hot stop.\n\n{JAMA_LINK}{url(101)}",
        priority="P2",
        has_condition=True,
    )
    unrelated = replace(
        agents,
        rid="ri.check.other",
        lineage="00000000-0000-4000-8000-000000000002",
        title="Mine",
        description="No link.",
    )
    nominal.add_checklist(PROPERTIES, [agents, unrelated])
    result = run(config, jama, nominal)
    assert outcomes(result) == {"WA-REQ-101": Outcome.UNCHANGED, "WA-REQ-102": Outcome.CREATED}
    assert [c.rid for c in nominal.only().checks][:2] == ["ri.check.agent", "ri.check.other"]


def test_test_cases_get_their_own_checklist(config: Config, jama: JamaClient, project: FakeJama) -> None:
    nominal = FakeChecklists()
    both = replace(config, jama=replace(config.jama, test_case_types=("35",)))
    run(both, jama, nominal)
    result = sync(checks_from_jama(both, jama=jama, kind=ItemKind.TEST_CASES), checklists=nominal)
    assert result.created
    assert outcomes(result) == {"WA-TC-201": Outcome.CREATED}
    names = {c.name: c.properties["jama_items"] for c in nominal.checklists.values()}
    assert names == {"Widget Assembly requirements": "requirements", "Widget Assembly test cases": "test_cases"}


def test_an_item_with_several_checks_keeps_them_as_they_are(
    config: Config, jama: JamaClient, project: FakeJama
) -> None:
    nominal = FakeChecklists()
    split = [
        ExistingCheck(
            rid=f"ri.check.{n}",
            lineage=f"00000000-0000-4000-8000-00000000000{n}",
            title=f"WA-REQ-101 Brake temperature: criterion {n}",
            description=f"Stays below 450°C during a hot stop.\n\n{JAMA_LINK}{url(101)}",
            priority="P2",
            has_condition=True,
        )
        for n in (1, 2)
    ]
    nominal.add_checklist(PROPERTIES, split)
    result = run(config, jama, nominal)
    assert [(r.title, r.outcome) for r in result.plan.results if r.item_id == "101"] == [
        ("WA-REQ-101 Brake temperature: criterion 1", Outcome.SEVERAL),
        ("WA-REQ-101 Brake temperature: criterion 2", Outcome.SEVERAL),
    ]
    assert [c.title for c in nominal.only().checks][:2] == [check.title for check in split]


def test_marked_channels_become_variables_once(config: Config, jama: JamaClient, project: FakeJama) -> None:
    project.set_field(101, "description", "<p>`brake_temp` stays below 450.</p>")
    nominal = FakeChecklists()
    first = run(config, jama, nominal)
    assert [(v.document_key, v.channel, v.name) for v in first.plan.variable_results] == [
        ("WA-REQ-101", "brake_temp", "a")
    ]
    second = run(config, jama, nominal)
    assert not second.plan.variable_results
    assert not second.committed


def test_an_existing_variable_for_the_channel_is_reused(config: Config, jama: JamaClient, project: FakeJama) -> None:
    nominal = FakeChecklists()
    run(config, jama, nominal)
    nominal.add_variable("a", channel="brake_temp")
    project.set_field(101, "description", "<p>`brake_temp` stays below 450.</p>")
    result = run(config, jama, nominal)
    assert not result.plan.variable_results


def test_two_checklists_for_the_project_stop_the_sync(config: Config, jama: JamaClient, project: FakeJama) -> None:
    nominal = FakeChecklists()
    nominal.add_checklist(PROPERTIES, [])
    nominal.add_checklist(PROPERTIES, [])
    with pytest.raises(SyncError, match="2 checklists"):
        run(config, jama, nominal)


def test_a_dry_run_writes_nothing(config: Config, jama: JamaClient, project: FakeJama) -> None:
    nominal = FakeChecklists()
    result = run(config, jama, nominal, dry_run=True)
    assert result.dry_run
    assert set(outcomes(result).values()) == {Outcome.CREATED}
    assert nominal.creates == 0


def test_a_conflict_is_raised(config: Config, jama: JamaClient, project: FakeJama) -> None:
    nominal = FakeChecklists()
    run(config, jama, nominal)
    project.set_field(101, "name", "Brake temperature limit")
    nominal.conflict_next = True
    with pytest.raises(ChecklistConflict):
        run(config, jama, nominal)


def test_settings_name_the_checklist_and_set_the_priority(config: Config, jama: JamaClient, project: FakeJama) -> None:
    nominal = FakeChecklists()
    settings = NominalSettings(checklist_name="Brakes", priority="P1")
    run(config, jama, nominal, nominal=settings)
    checklist = nominal.only()
    assert checklist.name == "Brakes"
    assert {c.priority for c in checklist.checks} == {"P1"}


# -- the command line ---------------------------------------------------------------------------


@pytest.fixture
def fake_nominal(monkeypatch: pytest.MonkeyPatch) -> FakeChecklists:
    nominal = FakeChecklists()
    monkeypatch.setattr(cli, "checklists_factory", lambda profile: nominal)
    return nominal


def test_sync_from_a_checks_file_needs_no_settings(
    tmp_path: Path, jama: JamaClient, project: FakeJama, fake_nominal: FakeChecklists, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = Config(jama=JamaSettings(base_url=BASE, project="12", item_types=("34",)))
    path = checks_from_jama(config, jama=jama).save(tmp_path / "checks.json")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["sync", "--from", str(path)])
    assert result.exit_code == 0, result.output
    assert "Created the checklist: 2 created." in result.output
    assert fake_nominal.creates == 1


def test_sync_prints_each_difference(
    tmp_path: Path, jama: JamaClient, project: FakeJama, fake_nominal: FakeChecklists, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = Config(jama=JamaSettings(base_url=BASE, project="12", item_types=("34",)))
    checks = checks_from_jama(config, jama=jama)
    sync(checks, checklists=fake_nominal)
    fake_nominal.edit("WA-REQ-102", title="WA-REQ-102 Pedal forse")
    path = checks.save(tmp_path / "checks.json")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["sync", "--from", str(path), "--update", "none"])
    assert result.exit_code == 0, result.output
    assert "differs from Jama, not updated: WA-REQ-102 Pedal forse" in result.output
    assert "-WA-REQ-102 Pedal forse" in result.output
    assert "+WA-REQ-102 Pedal force" in result.output
    assert Checks.load(path) == checks
