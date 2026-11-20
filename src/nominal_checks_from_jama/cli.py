"""The ``nominal-checks-from-jama`` command line interface."""

from __future__ import annotations

import difflib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click

from nominal_checks_from_jama._jama import JamaHTTPError, instance_url, project_in_url
from nominal_checks_from_jama._nominal import Checklists, NominalError, SdkChecklists
from nominal_checks_from_jama.agent_plan import write_agent_plan
from nominal_checks_from_jama.checks import Checks, build_checks
from nominal_checks_from_jama.config import DEFAULT_CONFIG, AuthKind, Config, JamaSettings, NominalSettings
from nominal_checks_from_jama.credentials import (
    CredentialsError,
    MissingSecretError,
    jama_client,
    load_secret,
    save_secret,
)
from nominal_checks_from_jama.discovery import DiscoveredType, Discovery, TypeCategory, discover
from nominal_checks_from_jama.files import FileFormatError
from nominal_checks_from_jama.kinds import ItemKind
from nominal_checks_from_jama.nominal_sync import Field, Outcome, SyncError, sync
from nominal_checks_from_jama.pipeline import checks_from_file, checks_from_jama
from nominal_checks_from_jama.requirements import ReadError, Requirements, read_requirements

_SECRET_PROMPT = "Secret (client secret, password or token)"

checklists_factory: Callable[[str], Checklists] = SdkChecklists.from_profile
"""Makes the Nominal connection from a profile name. Tests replace it."""

_ERRORS = (ReadError, SyncError, CredentialsError, NominalError, FileFormatError)

_FROM = click.option(
    "--from",
    "source",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="A file from step 1 or 2 to start from, such as requirements.json or checks.json, instead of reading Jama.",
)

_TEST_CASES = click.option(
    "--test-cases",
    "test_cases",
    is_flag=True,
    help="Work on the project's test cases, with their own files and checklist, instead of its requirements.",
)


def _output(help_text: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    return click.option(
        "-o",
        "--output",
        type=click.Path(dir_okay=False, path_type=Path),
        default=None,
        help=help_text,
    )


def _kind(test_cases: bool) -> ItemKind:
    return ItemKind.TEST_CASES if test_cases else ItemKind.REQUIREMENTS


def _same_kind(file_kind: ItemKind, source: Path, test_cases: bool) -> None:
    """Stop when ``--test-cases`` and the ``--from`` file disagree about what they hold."""
    if file_kind is not _kind(test_cases):
        flag = "leave out --test-cases" if file_kind is ItemKind.REQUIREMENTS else "add --test-cases"
        raise click.ClickException(f"{source} holds {file_kind.plural}: {flag}.")


def _command(subcommand: str) -> str:
    """A command as the reader runs it, such as ``python nominal-checks-from-jama.py init``.

    Each way of starting the tool sets the program name: the script, ``python -m`` and the
    installed command.
    """
    context = click.get_current_context(silent=True)
    program = context.find_root().info_name if context is not None else None
    return f"{program or 'nominal-checks-from-jama'} {subcommand}"


def _failure(error: Exception) -> click.ClickException:
    """An error for the terminal, with the command that fixes it where there is one."""
    if isinstance(error, MissingSecretError):
        return click.ClickException(f"{error} Run `{_command('login')}` to store it.")
    return click.ClickException(str(error))


def _load(path: Path) -> Config:
    try:
        return Config.load(path)
    except FileNotFoundError:
        raise click.ClickException(f"No settings file at {path}. Run `{_command('init')}` to create one.") from None
    except ValueError as error:
        raise click.ClickException(f"{path}: {error}") from None


def _nominal(path: Path) -> NominalSettings:
    """The [nominal] settings when the settings file exists, and the defaults when it doesn't."""
    return _load(path).nominal if path.exists() else NominalSettings()


def _checks(path: Path, source: Path | None, test_cases: bool) -> Checks:
    """The checks from ``source`` when given, and otherwise read from Jama with the settings."""
    try:
        if source is not None:
            checks = checks_from_file(source, markers=_nominal(path).channel_markers)
            _same_kind(checks.kind, source, test_cases)
            return checks
        return checks_from_jama(_load(path), kind=_kind(test_cases))
    except _ERRORS as error:
        raise _failure(error) from None
    except JamaHTTPError as error:
        raise click.ClickException(f"Couldn't read Jama: {error}") from None


@click.group(name="nominal-checks-from-jama")
@click.option(
    "--config",
    "config_path",
    type=click.Path(dir_okay=False, path_type=Path),
    default=DEFAULT_CONFIG,
    show_default=True,
    help="The settings file.",
)
@click.pass_context
def main(ctx: click.Context, config_path: Path) -> None:
    """Make Nominal checks from the requirements in a Jama Connect project."""
    ctx.obj = config_path


class _JamaURL(click.ParamType[str]):
    """A Jama URL, checked but kept as typed, so ``--project`` can read its project id."""

    name = "url"

    def convert(self, value: Any, param: click.Parameter | None, ctx: click.Context | None) -> str:
        try:
            instance_url(str(value))
        except ValueError as error:
            self.fail(str(error), param, ctx)
        return str(value).strip()


def _existing(path: Path) -> Config | None:
    """The settings file at ``path``, when it exists and reads."""
    if not path.exists():
        return None
    try:
        return Config.load(path)
    except (OSError, ValueError):
        return None


def _ask(
    text: str, given: str | None, default: str | None, *, skip: bool, kind: click.ParamType[str] | None = None
) -> str:
    """The value given as an option, else ``default`` when ``skip``, else the answer to a prompt offering it."""
    if given is not None:
        return given
    if skip and default:
        return default
    answer: str = click.prompt(text, default=default, type=kind)
    return answer


@main.command()
@click.option(
    "--base-url",
    type=_JamaURL(),
    help="The Jama Connect URL, such as https://example.jamacloud.com, or the URL of any page in Jama Connect.",
)
@click.option(
    "--project", help="The project id. When --base-url is a page in the project, its project id is the default."
)
@click.option(
    "--auth",
    type=click.Choice([kind.value for kind in AuthKind]),
    help="How to sign in: client_credentials unless the settings file says otherwise.",
)
@click.option("--account", help="The client ID, or the username for basic.")
@click.option(
    "--force",
    is_flag=True,
    help="Replace an existing settings file, offering its values as the answers. Keeps its [nominal] settings.",
)
@click.option(
    "--re-init",
    "re_init",
    is_flag=True,
    help="Read the project's item types again, with the settings file's URL, project and account, asking nothing.",
)
@click.pass_obj
def init(
    config_path: Path,
    base_url: str | None,
    project: str | None,
    auth: str | None,
    account: str | None,
    force: bool,
    re_init: bool,
) -> None:
    """Create the settings file, with the project's requirement and test case types filled in.

    It asks for the Jama Connect URL, the project id and the account, offering the settings file's
    values with --force. It asks for the secret if your operating system's credential manager
    doesn't have it, and stores it there. Run it again with --re-init after item types change in
    Jama Connect.
    """
    existing = _existing(config_path)
    if config_path.exists() and not (force or re_init):
        raise click.ClickException(f"{config_path} exists. Pass --force to replace it, or --re-init to read it again.")
    if re_init and existing is None:
        raise click.ClickException(f"No settings file at {config_path} to read again. Run `init` without --re-init.")
    old = existing.jama if existing else None
    base_url = _ask(
        "Jama Connect URL (paste it from your browser)",
        base_url,
        old.base_url if old else None,
        skip=re_init,
        kind=_JamaURL(),
    )
    # a pasted page's project id first, then the settings file's
    project = _ask("Jama project id", project, project_in_url(base_url) or (old.project if old else None), skip=re_init)
    account = _ask("API client ID, or username", account, (old.account or None) if old else None, skip=re_init)
    auth = auth or str(old.auth if old else AuthKind.CLIENT_CREDENTIALS)
    settings = JamaSettings(base_url=base_url.strip(), project=project.strip(), auth=AuthKind(auth), account=account)
    try:
        secret = load_secret(settings)
        click.echo("Using the secret stored in your operating system's credential manager.")
    except CredentialsError:
        secret = click.prompt(_SECRET_PROMPT, hide_input=True)
        try:
            save_secret(settings, secret)
        except CredentialsError as error:
            raise _failure(error) from None
        click.echo("Stored the secret in your operating system's credential manager.")
    # signing in and counting each item type's items takes a while, so say what's happening
    click.echo(f"Connecting to {settings.base_url} to read project {settings.project}'s item types...")
    try:
        with jama_client(settings, secret) as client:
            found = discover(client, settings.project)
    except JamaHTTPError as error:
        raise click.ClickException(f"Couldn't read the project: {error}") from None
    Config(
        jama=JamaSettings(
            base_url=settings.base_url,
            project=settings.project,
            item_types=found.requirement_types(),
            auth=settings.auth,
            account=settings.account,
            test_case_types=found.test_case_types(),
        ),
        nominal=existing.nominal if existing else NominalSettings(),
        path=config_path,
    ).save()

    for line in _summary(found):
        click.echo(line)
    click.echo(
        f"Wrote {config_path}. Check [jama] item_types and test_case_types, then run `{_command('agent-plan')}`."
    )


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _summary(found: Discovery) -> list[str]:
    """The item types ``init`` reads, and why it doesn't read the others, grouped by reason."""

    def named(discovered: DiscoveredType) -> str:
        t, count = discovered.item_type, discovered.count
        return f"{t.id} {t.display}" + ("" if count is None else f" ({_plural(count, 'item')})")

    def reading(types: list[DiscoveredType], what: str, where: str) -> list[str]:
        counts = [t.count for t in types if t.count is not None]
        total = f", {_plural(sum(counts), 'item')}" if len(counts) == len(types) else ""
        return [f"Reading {_plural(len(types), what)}{total}, {where}:", *(f"  {named(t)}" for t in types)]

    requirement_ids, test_case_ids = set(found.requirement_types()), set(found.test_case_types())
    requirements = [t for t in found.item_types if t.item_type.id in requirement_ids]
    test_cases = [t for t in found.item_types if t.item_type.id in test_case_ids]
    unread = [t for t in found.item_types if t.item_type.id not in requirement_ids | test_case_ids]
    containers = [t for t in unread if t.category is TypeCategory.CONTAINER]
    empty = [t for t in unread if t.category is not TypeCategory.CONTAINER and t.count == 0]
    # the rest have items, or Jama didn't say how many, and are neither requirement nor test case types
    other = [t for t in unread if t not in containers and t not in empty]

    lines = [f"Project {found.project.id}: {found.project.name}"]
    if requirements:
        lines += reading(requirements, "requirement type", "for the requirements checklist")
    else:
        lines.append("No item type looks like requirements. List their ids in [jama] item_types.")
    if test_cases:
        lines += reading(test_cases, "test case type", "for a separate test cases checklist")
    if unread:
        lines.append("Not reading:")
        lines += [f"  {named(t)}: not a requirement or test case type" for t in other]
        if empty:
            lines.append(f"  {_plural(len(empty), 'type')} with no items in this project")
        if containers:
            hold = "which holds" if len(containers) == 1 else "which hold"
            names = ", ".join(t.item_type.display for t in containers)
            lines.append(f"  {_plural(len(containers), 'container type')}, {hold} other items: {names}")
    return lines


@main.command()
@click.pass_obj
def login(config_path: Path) -> None:
    """Store the Jama secret in your operating system's credential manager, replacing any stored before."""
    config = _load(config_path)
    secret = click.prompt(_SECRET_PROMPT, hide_input=True)
    try:
        save_secret(config.jama, secret)
    except CredentialsError as error:
        raise _failure(error) from None
    click.echo(f"Stored the secret for {config.jama.account} at {config.jama.base_url}.")


@main.command("read")
@_TEST_CASES
@_output("The file to write: requirements.json, or test-cases.json with --test-cases.")
@click.pass_obj
def read_command(config_path: Path, test_cases: bool, output: Path | None) -> None:
    """Step 1: read the project's requirements, or its test cases, from Jama into a file."""
    kind = _kind(test_cases)
    try:
        requirements = read_requirements(_load(config_path), kind=kind)
    except _ERRORS as error:
        raise _failure(error) from None
    except JamaHTTPError as error:
        raise click.ClickException(f"Couldn't read Jama: {error}") from None
    written = requirements.save(output)
    click.echo(f"Wrote {written}: {kind.counted(len(requirements.requirements))}.")


@main.command("checks")
@_FROM
@_TEST_CASES
@_output("The file to write: checks.json, or test-checks.json for test cases.")
@click.pass_obj
def checks_command(config_path: Path, source: Path | None, test_cases: bool, output: Path | None) -> None:
    """Step 2: make a check for each requirement or test case, into a file."""
    if source is not None:
        try:
            items = Requirements.load(source)
            _same_kind(items.kind, source, test_cases)
            checks = build_checks(items, markers=_nominal(config_path).channel_markers)
        except _ERRORS as error:
            raise _failure(error) from None
    else:
        checks = _checks(config_path, None, test_cases)
    written = checks.save(output)
    count = len(checks.checks)
    marked = sum(len(check.channels) for check in checks.checks)
    checks_word = "check" if count == 1 else "checks"
    channels_word = "marked channel" if marked == 1 else "marked channels"
    click.echo(f"Wrote {written}: {count} {checks_word}, {marked} {channels_word}.")


@main.command("agent-plan")
@_FROM
@_TEST_CASES
@click.option("--target", help="The RID of the asset or run whose channels the conditions should use.")
@_output("The file to write: checks-plan.md, or test-checks-plan.md for test cases.")
@click.pass_obj
def agent_plan_command(
    config_path: Path, source: Path | None, test_cases: bool, target: str | None, output: Path | None
) -> None:
    """Write instructions for your agent to build the checklist and draft its conditions.

    Give the file to an agent connected to Nominal, such as Claude, ChatGPT or Nominal's Analyst. It
    keeps a check for each requirement, or as many as each test case's pass criteria need, in a draft
    of the checklist, and leaves publishing to you.
    """
    checks = _checks(config_path, source, test_cases)
    name = _nominal(config_path).checklist_name_for(checks.kind)
    written = write_agent_plan(checks, target=target, checklist_name=name, data_scope=_nominal(config_path).ref_name)
    path = output if output is not None else Path(checks.kind.plan_file)
    path.write_text(written.markdown, encoding="utf-8")
    click.echo(f"Wrote {path}: {checks.kind.counted(len(written.checks))}.")
    click.echo("Give it to your agent connected to Nominal, then review its draft before publishing.")


_UPDATE = {
    "all": (Field.TITLE, Field.DESCRIPTION),
    "title": (Field.TITLE,),
    "description": (Field.DESCRIPTION,),
    "none": (),
}

# The order outcomes are listed in: changes first, then what needs a person's attention.
_LISTED = (
    Outcome.CREATED,
    Outcome.UPDATED,
    Outcome.REMOVED,
    Outcome.DIFFERS,
    Outcome.CANT_UPDATE,
    Outcome.SEVERAL,
    Outcome.GONE,
)


def _show_difference(field: str, nominal: str, jama: str) -> None:
    lines = difflib.unified_diff(
        nominal.splitlines(), jama.splitlines(), fromfile="Nominal", tofile="Jama", lineterm="", n=0
    )
    click.echo(f"      {field}:")
    for line in lines:
        click.echo(f"        {line}")


@main.command("sync")
@_FROM
@_TEST_CASES
@click.option("--dry-run", is_flag=True, help="Show what's different from Jama, and write nothing.")
@click.option(
    "--update",
    type=click.Choice(list(_UPDATE)),
    default="all",
    show_default=True,
    help="What to rewrite from Jama in checks that differ: none only reports the differences.",
)
@click.option("--remove-missing", is_flag=True, help="Remove checks whose requirement or test case is gone from Jama.")
@click.pass_obj
def sync_command(
    config_path: Path, source: Path | None, test_cases: bool, dry_run: bool, update: str, remove_missing: bool
) -> None:
    """Create or update the checklist in Nominal, with a check for each requirement or test case.

    Jama is the source of truth for each check's title and description. Checks someone changed in
    Nominal are rewritten from Jama, keeping their conditions, unless --update says otherwise.
    Requirements and test cases each have their own checklist.
    """
    checks = _checks(config_path, source, test_cases)
    settings = _nominal(config_path)
    try:
        result = sync(
            checks,
            nominal=settings,
            update=_UPDATE[update],
            remove_missing=remove_missing,
            dry_run=dry_run,
            checklists=checklists_factory(settings.profile),
        )
    except _ERRORS as error:
        raise _failure(error) from None

    for outcome in _LISTED:
        for item in (r for r in result.plan.results if r.outcome is outcome):
            click.echo(f"  {outcome}: {item.title}")
            for difference in item.differences:
                _show_difference(difference.field, difference.nominal, difference.jama)
    for variable in result.plan.variable_results:
        click.echo(f"  variable added: {variable.document_key} `{variable.channel}` as {variable.name}")
    counts = result.plan.counts()
    summary = ", ".join(f"{count} {outcome}" for outcome, count in counts.items()) or f"no {checks.kind.plural}"
    if dry_run:
        click.echo(f"Dry run, nothing written: {summary}.")
    elif result.created:
        click.echo(f"Created the checklist: {summary}.")
    elif result.committed:
        click.echo(f"Committed a new version of the checklist: {summary}.")
    elif result.checklist_rid is None:
        click.echo(f"No {checks.kind.plural} found, so no checklist was created.")
    else:
        click.echo(f"The checklist is up to date: {summary}.")
    if result.checklist_url:
        click.echo(result.checklist_url)
