"""The agent output: checks-plan.md, written from the checks alone."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from nominal_checks_from_jama.agent_plan import TOOLS, write_agent_plan
from nominal_checks_from_jama.checks import Checks, build_checks
from nominal_checks_from_jama.cli import main
from nominal_checks_from_jama.kinds import ItemKind
from nominal_checks_from_jama.requirements import Requirement, Requirements, Source

from .conftest import BASE

SOURCE = Source(BASE, "12", "Widget Assembly")


def checks(*texts: str) -> Checks:
    requirements = tuple(
        Requirement(str(i), f"WA-REQ-{i}", f"Requirement {i}", text, f"<p>{text}</p>", f"{BASE}/item/{i}")
        for i, text in enumerate(texts, start=1)
    )
    return build_checks(Requirements(SOURCE, requirements))


def test_a_test_case_plan_lets_the_agent_split_by_pass_criteria(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_case = Requirement("7", "WA-TC-7", "Hot stop test", "Pass criteria: below 450 C.", "", f"{BASE}/item/7")
    test_checks = build_checks(Requirements(SOURCE, (test_case,), ItemKind.TEST_CASES))
    markdown = write_agent_plan(test_checks).markdown
    assert markdown.startswith("# Build a Nominal checklist from Jama test cases\n")
    assert "`jama_items` = `test_cases`" in markdown
    assert "create one named `Widget Assembly test cases`" in markdown
    assert "Make an appropriate number of checks to satisfy each test case's pass criteria" in markdown
    assert "Add a new check only together with its condition." in markdown
    assert "## Test cases (1)" in markdown
    # the CLI writes it to its own file, and won't mix the kinds up
    source = test_checks.save(tmp_path / "test-checks.json")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["agent-plan", "--test-cases", "--from", str(source)])
    assert result.exit_code == 0, result.output
    assert "Wrote test-checks-plan.md: 1 test case." in result.output
    assert (tmp_path / "test-checks-plan.md").exists()
    mixed = runner.invoke(main, ["agent-plan", "--from", str(source)])
    assert mixed.exit_code == 1
    assert "holds test cases: add --test-cases" in mixed.output


def test_the_plan_names_each_tool_and_what_it_is_for() -> None:
    markdown = write_agent_plan(checks("Text.")).markdown
    for tool, intent in TOOLS:
        names = ", ".join(f"`{name}`" for name in tool.split(", "))
        assert f"| {names} | {intent} |" in markdown
    assert "| `search_runs`, `search_assets` |" in markdown
    assert "use whichever tool does what the second column says" in markdown


def test_the_plan_finds_or_creates_the_checklist_by_its_properties() -> None:
    markdown = write_agent_plan(checks("Text.")).markdown
    assert "`jama_host` = `example.jamacloud.com`, `jama_project` = `12`" in markdown
    assert "create one named `Widget Assembly requirements`" in markdown
    assert "Don't publish" in markdown
    # sync compares the text with Jama exactly, so the agent leaves that to it
    assert "is the tool's `sync` command's job, so don't compare them yourself" in markdown
    assert "List the differences" not in markdown
    custom = write_agent_plan(checks("Text."), checklist_name="Brakes").markdown
    assert "create one named `Brakes`" in custom


def test_each_requirement_gives_the_exact_title_and_description() -> None:
    made = checks("Keep `brake_temp` below 450.")
    plan = write_agent_plan(made)
    (check,) = made.checks
    assert plan.checks == (check.title,)
    assert f"```text\n{check.title}\n```" in plan.markdown
    assert f"```text\n{check.description}\n```" in plan.markdown
    assert "- Channels the requirement marks: `brake_temp`" in plan.markdown


def test_text_with_backtick_fences_cant_end_its_block_early() -> None:
    plan = write_agent_plan(checks("Before\n```\nafter"))
    assert "````text\n" in plan.markdown


def test_the_target_is_named_or_the_agent_asks() -> None:
    assert (
        "the asset or run `ri.scout.test.run.1`"
        in write_agent_plan(checks("T."), target="ri.scout.test.run.1").markdown
    )
    unnamed = write_agent_plan(checks("T.")).markdown
    assert "ask them which; they may have none yet" in unnamed
    # a channel no data has yet is proposed in the settings' data scope, and saved without channelSource
    assert "in the data scope `default`" in unnamed
    assert "in the data scope `rig`" in write_agent_plan(checks("T."), data_scope="rig").markdown
    assert "a separate edit without it" in unnamed


def test_proposed_channels_are_listed_and_later_matched_to_the_data() -> None:
    markdown = write_agent_plan(checks("T.")).markdown
    assert "List every channel name you proposed, however many there are" in markdown
    assert "such as a name proposed earlier, find its channel that measures the same thing" in markdown
    assert "except its channel as step 6 says" in markdown
    # thresholds stay as stated, with or-equal comparisons rather than shifted values
    assert "`greaterThanEqual` or `lessThanEqual`" in markdown
    assert "its conditions are `lessThan` 10 or `greaterThan` 20" in markdown  # a range keeps both ends allowed
    # a delay between two signals is a state with time persistence, not a channel someone has to compute
    assert "set the check's time persistence (`timePersistence`) to T" in markdown
    assert "This works only while X stays set until Y happens" in markdown
    # a limit that holds only in a state is scoped by channels already in play, else a mode channel
    assert "computing a rate with `derivative` in a checklist variable" in markdown
    # the agent's notes go after the link line, which sync keeps
    assert "Put your notes there, after a line `Notes:`" in markdown
    assert "up to and including its `Jama:` line" in markdown
    test_case = Requirement("7", "WA-TC-7", "Hot stop test", "Pass criteria: below 450 C.", "", f"{BASE}/item/7")
    test_checks = build_checks(Requirements(SOURCE, (test_case,), ItemKind.TEST_CASES))
    assert "except its channel as step 7 says" in write_agent_plan(test_checks).markdown


def test_no_requirements() -> None:
    assert "There are no requirements." in write_agent_plan(Checks(SOURCE, ())).markdown


def test_agent_plan_from_a_checks_file_needs_no_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = checks("Text.", "More.").save(tmp_path / "checks.json")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["agent-plan", "--from", str(path), "--target", "ri.scout.test.run.1"])
    assert result.exit_code == 0, result.output
    assert "Wrote checks-plan.md: 2 requirements." in result.output
    assert "WA-REQ-2 Requirement 2" in (tmp_path / "checks-plan.md").read_text(encoding="utf-8")


def test_agent_plan_from_a_requirements_file_makes_the_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    requirements = Requirements(
        SOURCE, (Requirement("1", "WA-REQ-1", "R", "Keep {rpm} low.", "<p>Keep {rpm} low.</p>", f"{BASE}/item/1"),)
    )
    path = requirements.save(tmp_path / "requirements.json")
    (tmp_path / "jama-checks.toml").write_text(
        f'[jama]\nbase_url = "{BASE}"\nproject = "12"\n\n[nominal]\nchannel_markers = ["{{}}"]\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["agent-plan", "--from", str(path)])
    assert result.exit_code == 0, result.output
    assert "- Channels the requirement marks: `rpm`" in (tmp_path / "checks-plan.md").read_text(encoding="utf-8")
