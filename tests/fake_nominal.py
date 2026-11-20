"""An in-memory checklist service that behaves like Nominal's for what the sync does."""

from __future__ import annotations

import itertools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from nominal_checks_from_jama._nominal import (
    ChecklistConflict,
    ChecklistVersion,
    Entry,
    ExistingCheck,
    ExistingVariable,
    Keep,
    KeepVariable,
    NewCheck,
    NewVariable,
    Rewrite,
)


@dataclass
class FakeChecklist:
    name: str
    description: str
    properties: dict[str, str]
    commit: str
    checks: list[ExistingCheck]
    variables: list[ExistingVariable] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


def _stored_variable(variable: NewVariable) -> ExistingVariable:
    return ExistingVariable(variable.name, variable.display_name, variable.ref_name, variable.channel, raw=variable)


class FakeChecklists:
    """Checklists keyed by RID. Kept checks keep their RID; created ones get a new one, as in Nominal."""

    def __init__(self, normalize: Callable[[str], str] = lambda text: text) -> None:
        self.checklists: dict[str, FakeChecklist] = {}
        self.normalize = normalize
        self.creates = 0
        self.commits = 0
        self.conflict_next = False
        self._ids = itertools.count(1)

    def _next(self, kind: str) -> str:
        return f"ri.scout.test.{kind}.{next(self._ids)}"

    def _version(self, rid: str) -> ChecklistVersion:
        checklist = self.checklists[rid]
        return ChecklistVersion(rid, checklist.commit, tuple(checklist.checks), tuple(checklist.variables))

    def _stored(self, check: NewCheck) -> ExistingCheck:
        return ExistingCheck(
            rid=self._next("check"),
            lineage=check.lineage,
            title=check.title,
            description=self.normalize(check.description),
            priority=check.priority,
            has_condition=False,
        )

    def _rewritten(self, entry: Rewrite) -> ExistingCheck:
        return replace(
            entry.check, rid=self._next("check"), title=entry.title, description=self.normalize(entry.description)
        )

    def _entry(self, entry: Entry, by_rid: Mapping[str, ExistingCheck]) -> ExistingCheck:
        if isinstance(entry, Keep):
            return by_rid[entry.rid]
        if isinstance(entry, Rewrite):
            return self._rewritten(entry)
        return self._stored(entry)

    def find(self, properties: Mapping[str, str]) -> list[str]:
        return [
            rid
            for rid, checklist in self.checklists.items()
            if all(checklist.properties.get(k) == v for k, v in properties.items())
        ]

    def get(self, rid: str) -> ChecklistVersion:
        return self._version(rid)

    def create(
        self,
        name: str,
        description: str,
        properties: Mapping[str, str],
        checks: Sequence[NewCheck],
        variables: Sequence[NewVariable] = (),
    ) -> ChecklistVersion:
        self.creates += 1
        rid = self._next("checklist")
        self.checklists[rid] = FakeChecklist(
            name,
            description,
            dict(properties),
            self._next("commit"),
            [self._stored(c) for c in checks],
            [_stored_variable(v) for v in variables],
        )
        return self._version(rid)

    def commit(
        self,
        version: ChecklistVersion,
        entries: Sequence[Entry],
        variables: Sequence[NewVariable | KeepVariable],
        message: str,
    ) -> ChecklistVersion:
        checklist = self.checklists[version.rid]
        if self.conflict_next or version.commit != checklist.commit:
            self.conflict_next = False
            raise ChecklistConflict("The checklist changed in Nominal while syncing. Run the sync again.")
        self.commits += 1
        by_rid = {check.rid: check for check in checklist.checks}
        checklist.checks = [self._entry(e, by_rid) for e in entries]
        by_name = {v.name: v for v in version.variables}
        checklist.variables = [
            by_name[v.name] if isinstance(v, KeepVariable) else _stored_variable(v) for v in variables
        ]
        checklist.commit = self._next("commit")
        checklist.messages.append(message)
        return self._version(version.rid)

    def url(self, rid: str) -> str:
        return f"https://app.example.test/checklists/{rid}"

    # -- what a person, or an agent, does in the app ---------------------------------------------

    def only(self) -> FakeChecklist:
        (checklist,) = self.checklists.values()
        return checklist

    def add_checklist(self, properties: Mapping[str, str], checks: Sequence[ExistingCheck]) -> str:
        """A checklist made elsewhere, such as by an agent."""
        rid = self._next("checklist")
        self.checklists[rid] = FakeChecklist("Made elsewhere", "", dict(properties), self._next("commit"), list(checks))
        return rid

    def edit(self, title_prefix: str, **changes: Any) -> None:
        checklist = self.only()
        checklist.checks = [
            replace(c, rid=self._next("check"), **changes) if c.title.startswith(title_prefix) else c
            for c in checklist.checks
        ]
        checklist.commit = self._next("commit")

    def delete(self, title_prefix: str) -> None:
        checklist = self.only()
        checklist.checks = [c for c in checklist.checks if not c.title.startswith(title_prefix)]
        checklist.commit = self._next("commit")

    def add_variable(self, name: str, *, channel: str | None = None) -> None:
        checklist = self.only()
        ref = "default" if channel else None
        checklist.variables.append(ExistingVariable(name, name, ref, channel))
        checklist.commit = self._next("commit")
