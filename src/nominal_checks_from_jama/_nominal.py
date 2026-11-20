"""The checklist in Nominal. This is the only module that calls Nominal.

The Python client has no public way to create a check without a condition, so this uses the
generated checklist service through the client's own service handle, as the client's
``ChecklistBuilder.commit`` does. pyproject.toml pins ``nominal`` to the releases this was
tested with.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from nominal.core import NominalClient
    from nominal_api import scout_api, scout_checks_api


class NominalError(Exception):
    """Nominal refused a request, or returned something this tool can't use."""


class ChecklistConflict(NominalError):
    """Someone committed to the checklist between the tool reading it and committing."""


@dataclass(frozen=True)
class ExistingCheck:
    """A check in the checklist as Nominal returned it.

    Attributes:
        rid (str): The check's RID.
        lineage (str): Its lineage, as a bare UUID.
        title (str): Its title.
        description (str): Its description.
        priority (str): Its priority, ``P0`` to ``P4``.
        has_condition (bool): Whether it has a condition.
        copyable (bool): Whether the tool can rewrite its text and keep the rest, condition included.
        raw (object): The check as Nominal returned it, for a rewrite.
    """

    rid: str
    lineage: str
    title: str
    description: str
    priority: str
    has_condition: bool
    copyable: bool = True
    raw: object = None


@dataclass(frozen=True)
class ExistingVariable:
    """A checklist variable as Nominal returned it.

    Attributes:
        name (str): Its ID in the checklist, such as ``a``.
        display_name (str | None): Its display name.
        ref_name (str | None): The data source it reads, when it's a channel.
        channel (str | None): The channel it reads, when it's a channel.
        raw (object): What a commit sends back to keep it unchanged.
    """

    name: str
    display_name: str | None
    ref_name: str | None
    channel: str | None
    raw: object = None


@dataclass(frozen=True)
class NewCheck:
    """A check to create.

    Attributes:
        lineage (str): The lineage.
        title (str): The title.
        description (str): The description.
        priority (str): The priority.
    """

    lineage: str
    title: str
    description: str
    priority: str


@dataclass(frozen=True)
class Keep:
    """A check to send back unchanged.

    Attributes:
        rid (str): The check's RID.
    """

    rid: str


@dataclass(frozen=True)
class Rewrite:
    """A check to send back with a new title or description, and everything else unchanged.

    Attributes:
        check (ExistingCheck): The check.
        title (str): Its new title.
        description (str): Its new description.
    """

    check: ExistingCheck
    title: str
    description: str


@dataclass(frozen=True)
class NewVariable:
    """A checklist variable to create for a channel.

    Attributes:
        name (str): Its ID in the checklist.
        display_name (str): Its display name.
        ref_name (str): The data source it reads.
        channel (str): The channel it reads.
    """

    name: str
    display_name: str
    ref_name: str
    channel: str


@dataclass(frozen=True)
class KeepVariable:
    """A checklist variable to send back unchanged.

    Attributes:
        name (str): Its ID in the checklist.
    """

    name: str


Entry = NewCheck | Keep | Rewrite
"""One check in a commit."""


@dataclass(frozen=True)
class ChecklistVersion:
    """The latest version of a checklist.

    Attributes:
        rid (str): The checklist's RID.
        commit (str): The commit id.
        checks (tuple[ExistingCheck, ...]): Its checks, in order.
        variables (tuple[ExistingVariable, ...]): Its checklist variables, in order.
    """

    rid: str
    commit: str
    checks: tuple[ExistingCheck, ...]
    variables: tuple[ExistingVariable, ...] = ()


class Checklists(Protocol):
    """What the sync needs from Nominal. Tests use an in-memory one."""

    def find(self, properties: Mapping[str, str]) -> list[str]:
        """The RIDs of published, unarchived checklists with all of these properties."""
        ...

    def get(self, rid: str) -> ChecklistVersion:
        """A checklist's latest version on main."""
        ...

    def create(
        self,
        name: str,
        description: str,
        properties: Mapping[str, str],
        checks: Sequence[NewCheck],
        variables: Sequence[NewVariable],
    ) -> ChecklistVersion:
        """Create and publish a checklist."""
        ...

    def commit(
        self,
        version: ChecklistVersion,
        entries: Sequence[Entry],
        variables: Sequence[NewVariable | KeepVariable],
        message: str,
    ) -> ChecklistVersion:
        """Replace the checks and variables of ``version``'s checklist."""
        ...

    def url(self, rid: str) -> str:
        """The checklist's URL in the Nominal app."""
        ...


def _bare_lineage(value: str | None) -> str:
    """A check lineage as a bare UUID. Nominal returns it as a RID ending in the UUID."""
    found = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", value or "")
    return found.group(0) if found else (value or "")


class SdkChecklists:
    """:class:`Checklists` on the Nominal Python client."""

    def __init__(self, client: NominalClient) -> None:
        """Wrap a connected client.

        Args:
            client (NominalClient): The client.
        """
        self._client = client

    @classmethod
    def from_profile(cls, profile: str) -> SdkChecklists:
        """Connect with a profile from the Nominal config file.

        Args:
            profile (str): The profile name.

        Returns:
            SdkChecklists: The connection.
        """
        from nominal.core import NominalClient

        return cls(NominalClient.from_profile(profile))

    def _call(
        self, what: str, request: Callable[[], scout_checks_api.VersionedChecklist]
    ) -> scout_checks_api.VersionedChecklist:
        from conjure_python_client import ConjureHTTPError

        try:
            return request()
        except ConjureHTTPError as error:
            if error.error_code == "CONFLICT":
                raise ChecklistConflict("The checklist changed in Nominal while syncing. Run the sync again.") from None
            raise NominalError(f"Nominal refused to {what} the checklist: {error.error_name or error}") from None

    def find(self, properties: Mapping[str, str]) -> list[str]:
        """The RIDs of published, unarchived checklists with all of these properties.

        Args:
            properties (Mapping[str, str]): The properties.

        Returns:
            list[str]: The RIDs.
        """
        return [checklist.rid for checklist in self._client.search_checklists(properties=dict(properties))]

    def get(self, rid: str) -> ChecklistVersion:
        """A checklist's latest version on main.

        Args:
            rid (str): The checklist's RID.

        Returns:
            ChecklistVersion: The version.
        """
        clients = self._client._clients
        return self._version(self._call("read", lambda: clients.checklist.get(clients.auth_header, rid)))

    def create(
        self,
        name: str,
        description: str,
        properties: Mapping[str, str],
        checks: Sequence[NewCheck],
        variables: Sequence[NewVariable],
    ) -> ChecklistVersion:
        """Create and publish a checklist, assigned to the signed-in user.

        Args:
            name (str): The checklist's name.
            description (str): Its description.
            properties (Mapping[str, str]): Its properties.
            checks (Sequence[NewCheck]): Its checks.
            variables (Sequence[NewVariable]): Its variables.

        Returns:
            ChecklistVersion: The new checklist.
        """
        from nominal_api import scout_checks_api

        clients = self._client._clients
        request = scout_checks_api.CreateChecklistRequest(
            commit_message="Created from Jama requirements",
            assignee_rid=self._client.get_user().rid,
            title=name,
            description=description,
            checks=[scout_checks_api.CreateChecklistEntryRequest(create_check=_create(check)) for check in checks],
            properties=dict(properties),
            labels=[],
            checklist_variables=[_new_variable(v) for v in variables],
            is_published=True,
            workspace=self._client._workspace_rid_for_search(None),
        )
        return self._version(self._call("create", lambda: clients.checklist.create(clients.auth_header, request)))

    def commit(
        self,
        version: ChecklistVersion,
        entries: Sequence[Entry],
        variables: Sequence[NewVariable | KeepVariable],
        message: str,
    ) -> ChecklistVersion:
        """Replace the checklist's checks and variables in a new commit on main.

        Args:
            version (ChecklistVersion): The version the entries were planned from.
            entries (Sequence[Entry]): Every check the new version has.
            variables (Sequence[NewVariable | KeepVariable]): Every variable it has.
            message (str): The commit message.

        Returns:
            ChecklistVersion: The new version.
        """
        from nominal_api import scout_checks_api

        existing = {v.name: v.raw for v in version.variables}
        clients = self._client._clients
        request = scout_checks_api.CommitChecklistRequest(
            checks=[_entry(entry) for entry in entries],
            checklist_variables=[
                existing[v.name] if isinstance(v, KeepVariable) else _new_variable(v)  # type: ignore[misc]
                for v in variables
            ],
            commit_message=message,
            latest_commit=version.commit,
        )
        return self._version(
            self._call("commit to", lambda: clients.checklist.commit(clients.auth_header, version.rid, request))
        )

    def url(self, rid: str) -> str:
        """The checklist's URL in the Nominal app.

        Args:
            rid (str): The checklist's RID.

        Returns:
            str: The URL.
        """
        return self._client.get_checklist(rid).nominal_url

    @staticmethod
    def _version(raw: scout_checks_api.VersionedChecklist) -> ChecklistVersion:
        from nominal_api import scout_checks_api

        if raw.functions:
            raise NominalError(
                "The checklist has functions, which this tool can't send back unchanged, so it won't commit to it."
            )
        checks = tuple(
            ExistingCheck(
                rid=entry.check.rid,
                lineage=_bare_lineage(entry.check.check_lineage_rid),
                title=entry.check.title,
                description=entry.check.description,
                priority=entry.check.priority.value,
                has_condition=_has_condition(entry.check.condition),
                copyable=_copyable(entry.check.condition),
                raw=entry.check,
            )
            for entry in raw.checks
            if entry.check is not None
        )
        variables = tuple(
            ExistingVariable(
                name=variable.name,
                display_name=variable.display_name,
                ref_name=series.data_source_ref if series is not None else None,
                channel=series.channel if series is not None else None,
                raw=scout_checks_api.UnresolvedChecklistVariable(
                    name=variable.name,
                    display_name=variable.display_name,
                    value=_unresolved_locator(variable.value),
                    compute_expression=variable.compute_expression,
                ),
            )
            for variable in raw.checklist_variables
            for series in [_series(variable.value)]
        )
        return ChecklistVersion(rid=raw.rid, commit=raw.commit.id, checks=checks, variables=variables)


def _entry(entry: Entry) -> scout_checks_api.UpdateChecklistEntryRequest:
    from nominal_api import scout_checks_api

    if isinstance(entry, Keep):
        return scout_checks_api.UpdateChecklistEntryRequest(check=entry.rid)
    if isinstance(entry, Rewrite):
        return scout_checks_api.UpdateChecklistEntryRequest(create_check=_rewrite(entry))
    return scout_checks_api.UpdateChecklistEntryRequest(create_check=_create(entry))


def _has_condition(condition: scout_checks_api.CheckCondition | None) -> bool:
    """Whether a check has a condition. The app's editor saves a check with none as an empty intersection."""
    if condition is None:
        return False
    ranges = condition.num_ranges_v3
    if ranges is None or ranges.compute_expression is not None:
        return True
    combined = ranges.ranges.intersect_range or ranges.ranges.union_range
    return combined is None or bool(combined.inputs)


def _copyable(condition: scout_checks_api.CheckCondition | None) -> bool:
    """Whether :func:`_unresolved_condition` can copy a condition: the kinds the Python client's copy helper copies."""
    if condition is None:
        return True
    return any(
        kind is not None
        for kind in (condition.num_ranges_v2, condition.num_ranges_v3, condition.parameterized_num_ranges_v1)
    )


def _series(locator: scout_checks_api.VariableLocator) -> scout_api.ChannelLocator | None:
    """The channel a variable is, or None when it's something else.

    The app's editor saves a channel variable as a compute node that passes one series through.
    """
    node = locator.compute_node
    if (
        locator.series is not None
        or node is None
        or node.series_node.raw is None
        or node.context.sub_function_variables
    ):
        return locator.series
    inner = node.context.variables.get(node.series_node.raw.name)
    return inner.series if inner is not None else None


def _create(check: NewCheck) -> scout_checks_api.CreateCheckRequest:
    from nominal_api import scout_api, scout_checks_api

    return scout_checks_api.CreateCheckRequest(
        title=check.title,
        description=check.description,
        priority=scout_api.Priority(check.priority),
        check_lineage_rid=check.lineage,
        condition=None,
    )


def _rewrite(entry: Rewrite) -> scout_checks_api.CreateCheckRequest:
    """The check with the new title and description, and everything else as it was.

    Mirrors the Python client's ``_to_create_check_request``, which copies a check this way.
    """
    from nominal_api import scout_checks_api

    raw = entry.check.raw
    if not isinstance(raw, scout_checks_api.Check) or not entry.check.copyable:
        raise NominalError(f"The tool can't copy the check {entry.check.title!r}, so it can't change its text.")
    return scout_checks_api.CreateCheckRequest(
        check_lineage_rid=entry.check.lineage,
        title=entry.title,
        description=entry.description,
        auto_generated_title=raw.auto_generated_title,
        auto_generated_description=raw.auto_generated_description,
        priority=raw.priority,
        generated_event_type=raw.generated_event_type,
        generated_event_labels=raw.generated_event_labels,
        condition=_unresolved_condition(raw.condition),
    )


def _unresolved_condition(
    condition: scout_checks_api.CheckCondition | None,
) -> scout_checks_api.UnresolvedCheckCondition | None:
    """A condition as a commit sends it. Mirrors the Python client's ``_to_unresolved_condition``."""
    from nominal_api import scout_checks_api

    if condition is None:
        return None
    if condition.num_ranges_v2 is not None:
        v2 = condition.num_ranges_v2
        return scout_checks_api.UnresolvedCheckCondition(
            num_ranges_v2=scout_checks_api.UnresolvedNumRangesConditionV2(
                ranges=v2.ranges,
                function_spec=v2.function_spec,
                threshold=v2.threshold,
                operator=v2.operator,
                variables={name: _unresolved_locator(value) for name, value in v2.variables.items()},
            )
        )
    if condition.num_ranges_v3 is not None:
        v3 = condition.num_ranges_v3
        return scout_checks_api.UnresolvedCheckCondition(
            num_ranges_v3=scout_checks_api.UnresolvedNumRangesConditionV3(
                ranges=v3.ranges,
                function_spec=v3.function_spec,
                threshold=v3.threshold,
                operator=v3.operator,
                variables={name: _unresolved_locator(value) for name, value in v3.variables.items()},
            )
        )
    if condition.parameterized_num_ranges_v1 is not None:
        param = condition.parameterized_num_ranges_v1
        return scout_checks_api.UnresolvedCheckCondition(
            parameterized_num_ranges_v1=scout_checks_api.UnresolvedParameterizedNumRangesConditionV1(
                ranges=param.ranges,
                implementations=[
                    scout_checks_api.UnresolvedVariables(
                        variables={name: _unresolved_locator(value) for name, value in impl.variables.items()}
                    )
                    for impl in param.implementations
                ],
            )
        )
    raise NominalError("A check has a kind of condition this tool can't copy.")


def _new_variable(variable: NewVariable) -> scout_checks_api.UnresolvedChecklistVariable:
    from nominal_api import scout_api, scout_checks_api

    return scout_checks_api.UnresolvedChecklistVariable(
        name=variable.name,
        display_name=variable.display_name,
        value=scout_checks_api.UnresolvedVariableLocator(
            series=scout_api.ChannelLocator(channel=variable.channel, data_source_ref=variable.ref_name, tags={})
        ),
    )


def _unresolved_locator(locator: scout_checks_api.VariableLocator) -> scout_checks_api.UnresolvedVariableLocator:
    """A variable's value as a commit sends it back, unchanged. Mirrors the Python client's own copy helper."""
    from nominal_api import scout_checks_api

    if locator.checklist_variable is not None:
        return scout_checks_api.UnresolvedVariableLocator(checklist_variable=locator.checklist_variable)
    if locator.series is not None:
        return scout_checks_api.UnresolvedVariableLocator(series=locator.series)
    if locator.timestamp is not None:
        return scout_checks_api.UnresolvedVariableLocator(timestamp=locator.timestamp)
    if locator.compute_node is not None and not locator.compute_node.context.sub_function_variables:
        node = locator.compute_node
        return scout_checks_api.UnresolvedVariableLocator(
            compute_node=scout_checks_api.UnresolvedComputeNodeWithContext(
                series_node=node.series_node,
                context=scout_checks_api.UnresolvedVariables(
                    variables={name: _unresolved_locator(value) for name, value in node.context.variables.items()}
                ),
            )
        )
    raise NominalError("The checklist has a variable of a kind this tool can't send back unchanged.")
