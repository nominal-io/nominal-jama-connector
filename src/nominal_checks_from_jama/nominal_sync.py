"""Output: keep a Nominal checklist in line with the checks from step 2.

Jama is the source of truth for every check's title and description. A sync reads the checklist
and the checks, and:

- creates a check for each requirement or test case that has none,
- reports each check whose title or description differs from Jama, and rewrites the fields you
  choose, keeping its condition and everything else,
- reports each check whose item is gone from Jama, and removes it only when you ask,
- reports an item that has more than one check, such as a test case an agent split by its pass
  criteria, and leaves those checks as they are,
- adds a checklist variable for each marked channel that has none,
- leaves every other check and variable alone.

It finds an item's check by its lineage, which the tool sets when it creates the check, or by the
line in its description that links to the item, which an agent's checks have too. Requirements and
test cases each have their own checklist. Nothing is kept on disk between syncs.
"""

from __future__ import annotations

import itertools
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum

import httpx

from nominal_checks_from_jama._nominal import (
    Checklists,
    ChecklistVersion,
    Entry,
    ExistingCheck,
    ExistingVariable,
    Keep,
    KeepVariable,
    NewCheck,
    NewVariable,
    Rewrite,
    SdkChecklists,
)
from nominal_checks_from_jama.checks import Checks, CheckSpec, linked_item, split_notes
from nominal_checks_from_jama.config import NominalSettings
from nominal_checks_from_jama.kinds import ItemKind
from nominal_checks_from_jama.requirements import Source


class SyncError(Exception):
    """The sync stopped before changing anything in Nominal."""


class Field(StrEnum):
    """A part of a check that comes from Jama."""

    TITLE = "title"
    DESCRIPTION = "description"


class Outcome(StrEnum):
    """What a sync did with one requirement's check."""

    CREATED = "created"
    UPDATED = "updated from Jama"
    UNCHANGED = "unchanged"
    DIFFERS = "differs from Jama, not updated"
    CANT_UPDATE = "differs from Jama, not updated: the tool can't copy its condition"
    GONE = "gone from Jama, kept"
    REMOVED = "gone from Jama, removed"
    SEVERAL = "has more than one check, left as they are"
    """Such as a test case an agent split into a check for each pass criterion."""


_CHANGES = frozenset({Outcome.CREATED, Outcome.UPDATED, Outcome.REMOVED})


@dataclass(frozen=True)
class Difference:
    """One field where a check differs from its requirement.

    Attributes:
        field (Field): The field.
        nominal (str): What the check has.
        jama (str): What the requirement makes it.
    """

    field: Field
    nominal: str
    jama: str


@dataclass(frozen=True)
class Result:
    """One requirement's outcome.

    Attributes:
        item_id (str): The requirement's Jama item id.
        title (str): Its check's title.
        outcome (Outcome): What happened.
        differences (tuple[Difference, ...]): Where the check differed from Jama.
    """

    item_id: str
    title: str
    outcome: Outcome
    differences: tuple[Difference, ...] = ()


@dataclass(frozen=True)
class VariableResult:
    """A checklist variable the sync added for a marked channel.

    Attributes:
        document_key (str): The requirement's document key.
        channel (str): The channel.
        name (str): The variable's ID in the checklist.
    """

    document_key: str
    channel: str
    name: str


@dataclass(frozen=True)
class SyncPlan:
    """The checklist's checks and variables after a sync, and what changed.

    Attributes:
        entries (tuple[Entry, ...]): Every check, in order: existing checks where they were, new
            ones after them.
        variables (tuple[NewVariable | KeepVariable, ...]): Every checklist variable, in order.
        results (tuple[Result, ...]): One per requirement, and per check whose requirement is gone.
        variable_results (tuple[VariableResult, ...]): One per variable added.
    """

    entries: tuple[Entry, ...]
    variables: tuple[NewVariable | KeepVariable, ...]
    results: tuple[Result, ...]
    variable_results: tuple[VariableResult, ...] = ()

    @property
    def changed(self) -> bool:
        """Whether the checklist needs a new commit.

        Returns:
            bool: True when a check is created, updated or removed, or a variable is added.
        """
        return any(r.outcome in _CHANGES for r in self.results) or bool(self.variable_results)

    def counts(self) -> dict[Outcome, int]:
        """How many requirements had each outcome.

        Returns:
            dict[Outcome, int]: The counts, for the outcomes that occurred.
        """
        counts: dict[Outcome, int] = {}
        for result in self.results:
            counts[result.outcome] = counts.get(result.outcome, 0) + 1
        return counts


@dataclass(frozen=True)
class SyncResult:
    """What a sync found and did.

    Attributes:
        plan (SyncPlan): Each requirement's outcome, and the checks committed.
        checklist_rid (str | None): The checklist, or None when there is none yet.
        checklist_url (str | None): Its URL in the Nominal app.
        created (bool): Whether this sync created the checklist.
        committed (bool): Whether this sync committed a new version of it.
        dry_run (bool): Whether this was a dry run, which writes nothing.
    """

    plan: SyncPlan
    checklist_rid: str | None
    checklist_url: str | None
    created: bool
    committed: bool
    dry_run: bool


def checklist_properties(source: Source, kind: ItemKind = ItemKind.REQUIREMENTS) -> dict[str, str]:
    """The properties that mark a checklist as the one for a Jama project's requirements or test cases.

    Args:
        source (Source): The Jama project.
        kind (ItemKind): Requirements or test cases, which each have their own checklist.

    Returns:
        dict[str, str]: ``jama_host``, ``jama_project`` and ``jama_items``.
    """
    return {
        "jama_host": (httpx.URL(source.base_url).host or "").lower(),
        "jama_project": source.project,
        "jama_items": str(kind),
    }


def checklist_name(source: Source, kind: ItemKind, name: str = "") -> str:
    """A new checklist's name.

    Args:
        source (Source): The Jama project.
        kind (ItemKind): Requirements or test cases.
        name (str): The name the settings give, if any.

    Returns:
        str: ``name``, or ``<project name> requirements`` or ``<project name> test cases``.
    """
    return name or f"{source.project_name} {kind.plural}"


def _same(a: str, b: str) -> bool:
    """Whether two texts match once runs of whitespace are made one space, so storage differences don't count."""
    return " ".join(a.split()) == " ".join(b.split())


def _differences(check: ExistingCheck, spec: CheckSpec) -> tuple[Difference, ...]:
    """Where the check differs from Jama. Its description counts only up to its link line: notes after it don't."""
    found: list[Difference] = []
    if not _same(check.title, spec.title):
        found.append(Difference(Field.TITLE, check.title, spec.title))
    text, _notes = split_notes(check.description, spec.url)
    if not _same(text, spec.description):
        found.append(Difference(Field.DESCRIPTION, text, spec.description))
    return tuple(found)


def plan_sync(
    checks: Checks,
    version: ChecklistVersion | None,
    *,
    priority: str = "P3",
    ref_name: str = "default",
    update: Iterable[Field] = (Field.TITLE, Field.DESCRIPTION),
    remove_missing: bool = False,
) -> SyncPlan:
    """Work out the checklist's checks and variables from the checks and the checklist as it is.

    Args:
        checks (Checks): The checks, from step 2.
        version (ChecklistVersion | None): The checklist's latest version; None for a new checklist.
        priority (str): The priority of new checks.
        ref_name (str): The data source new variables read.
        update (Iterable[Field]): The fields to rewrite from Jama where a check differs. Empty to
            only report differences.
        remove_missing (bool): Remove checks whose requirement is gone from Jama, rather than
            reporting them.

    Returns:
        SyncPlan: The checks and variables to commit, and what happened to each.
    """
    rewrite = frozenset(update)
    specs = {spec.item_id: spec for spec in checks.checks}
    by_lineage = {spec.lineage: spec for spec in checks.checks}
    existing = version.checks if version is not None else ()

    def item_of(check: ExistingCheck) -> str | None:
        spec = by_lineage.get(check.lineage)
        return spec.item_id if spec is not None else linked_item(check.description, checks.source)

    owners = [(check, item_of(check)) for check in existing]
    per_item = Counter(item_id for _, item_id in owners if item_id is not None)

    entries: list[Entry] = []
    results: list[Result] = []
    matched: set[str] = set()
    for check, item_id in owners:
        if item_id is not None and item_id not in specs:
            if remove_missing:
                results.append(Result(item_id, check.title, Outcome.REMOVED))
            else:
                entries.append(Keep(check.rid))
                results.append(Result(item_id, check.title, Outcome.GONE))
            continue
        if item_id is None:
            entries.append(Keep(check.rid))  # not a check for a Jama item
            continue
        matched.add(item_id)
        if per_item[item_id] > 1:
            # an agent may split one item into several checks; rewriting one from Jama would undo that
            entries.append(Keep(check.rid))
            results.append(Result(item_id, check.title, Outcome.SEVERAL))
            continue
        entry, result = _compare(check, specs[item_id], rewrite)
        entries.append(entry)
        results.append(result)

    for spec in checks.checks:
        if spec.item_id not in matched:
            entries.append(NewCheck(spec.lineage, spec.title, spec.description, priority))
            results.append(Result(spec.item_id, spec.title, Outcome.CREATED))

    variables, variable_results = _plan_variables(checks.checks, version.variables if version else (), ref_name)
    return SyncPlan(tuple(entries), variables, tuple(results), variable_results)


def _compare(check: ExistingCheck, spec: CheckSpec, rewrite: frozenset[Field]) -> tuple[Entry, Result]:
    differences = _differences(check, spec)
    if not differences:
        return Keep(check.rid), Result(spec.item_id, check.title, Outcome.UNCHANGED)
    if not any(d.field in rewrite for d in differences):
        return Keep(check.rid), Result(spec.item_id, check.title, Outcome.DIFFERS, differences)
    if not check.copyable:
        return Keep(check.rid), Result(spec.item_id, check.title, Outcome.CANT_UPDATE, differences)
    title = spec.title if Field.TITLE in rewrite else check.title
    description = check.description
    if Field.DESCRIPTION in rewrite:
        # Jama's text up to the link line, then the notes the check already had
        _text, notes = split_notes(check.description, spec.url)
        description = f"{spec.description}\n\n{notes}" if notes else spec.description
    return Rewrite(check, title, description), Result(spec.item_id, title, Outcome.UPDATED, differences)


def _variable_name(index: int) -> str:
    """The IDs the app gives variables: a, ..., z, aa, ..., az, ba, ..."""
    name = ""
    while index >= 0:
        index, remainder = divmod(index, 26)
        name = chr(ord("a") + remainder) + name
        index -= 1
    return name


def _plan_variables(
    specs: Sequence[CheckSpec], existing: Sequence[ExistingVariable], ref_name: str
) -> tuple[tuple[NewVariable | KeepVariable, ...], tuple[VariableResult, ...]]:
    have = {(v.ref_name, v.channel) for v in existing if v.channel is not None}
    taken = {v.name for v in existing}
    names = (_variable_name(i) for i in itertools.count())
    entries: list[NewVariable | KeepVariable] = [KeepVariable(v.name) for v in existing]
    added: list[VariableResult] = []
    for spec in specs:
        for channel in spec.channels:
            if (ref_name, channel) in have:
                continue
            name = next(n for n in names if n not in taken)
            taken.add(name)
            have.add((ref_name, channel))
            entries.append(NewVariable(name, f"{spec.document_key}: {channel}", ref_name, channel))
            added.append(VariableResult(spec.document_key, channel, name))
    return tuple(entries), tuple(added)


def _commit_message(plan: SyncPlan, kind: ItemKind) -> str:
    counts = plan.counts()
    parts = [
        f"{counts[outcome]} {word}"
        for outcome, word in ((Outcome.CREATED, "added"), (Outcome.UPDATED, "updated"), (Outcome.REMOVED, "removed"))
        if outcome in counts
    ]
    if plan.variable_results:
        count = len(plan.variable_results)
        parts.append(f"{count} variable{'' if count == 1 else 's'} added")
    return f"From Jama {kind.plural}: " + ", ".join(parts)


def sync(
    checks: Checks,
    *,
    nominal: NominalSettings | None = None,
    update: Iterable[Field] = (Field.TITLE, Field.DESCRIPTION),
    remove_missing: bool = False,
    dry_run: bool = False,
    checklists: Checklists | None = None,
) -> SyncResult:
    """Bring the Nominal checklist for the checks' Jama project in line with them.

    The first sync creates and publishes the checklist. Later syncs find it by its properties,
    ``jama_host``, ``jama_project`` and ``jama_items``. Requirements and test cases each have
    their own checklist.

    Args:
        checks (Checks): The checks, from step 2.
        nominal (NominalSettings | None): The profile, priority, data source and checklist name to
            use; the defaults when None.
        update (Iterable[Field]): The fields to rewrite from Jama where a check differs. Empty to
            only report differences.
        remove_missing (bool): Remove checks whose requirement is gone from Jama, rather than
            reporting them.
        dry_run (bool): Work out the changes, but write nothing to Nominal.
        checklists (Checklists | None): The Nominal connection; one from the profile when None.

    Returns:
        SyncResult: What it found and did.

    Raises:
        SyncError: When more than one checklist is for the Jama project.
    """
    settings = nominal or NominalSettings()
    service = checklists or SdkChecklists.from_profile(settings.profile)
    properties = checklist_properties(checks.source, checks.kind)
    found = service.find(properties)
    if len(found) > 1:
        raise SyncError(
            f"{len(found)} checklists in Nominal are for this Jama project's {checks.kind.plural}. "
            "Archive the extra ones, then run the sync again."
        )
    rid = found[0] if found else None
    version = service.get(rid) if rid is not None else None
    plan = plan_sync(
        checks,
        version,
        priority=settings.priority,
        ref_name=settings.ref_name,
        update=update,
        remove_missing=remove_missing,
    )
    if dry_run:
        return SyncResult(plan, rid, service.url(rid) if rid else None, False, False, True)
    if version is None:
        new = [entry for entry in plan.entries if isinstance(entry, NewCheck)]
        if not new:
            return SyncResult(plan, None, None, False, False, False)
        source, kind = checks.source, checks.kind
        name = checklist_name(source, kind, settings.checklist_name_for(kind))
        described = kind.plural.capitalize()
        description = f"{described} from Jama project {source.project} ({source.project_name}), one check each."
        variables = [v for v in plan.variables if isinstance(v, NewVariable)]
        version = service.create(name, description, properties, new, variables)
        return SyncResult(plan, version.rid, service.url(version.rid), True, False, False)
    if plan.changed:
        version = service.commit(version, plan.entries, plan.variables, _commit_message(plan, checks.kind))
        return SyncResult(plan, version.rid, service.url(version.rid), False, True, False)
    return SyncResult(plan, version.rid, service.url(version.rid), False, False, False)
