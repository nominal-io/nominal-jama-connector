"""SdkChecklists against a stand-in for the client's checklist service, with the real request types."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import requests
from conjure_python_client import ConjureHTTPError
from nominal_api import event, scout_api, scout_checks_api, scout_compute_api, scout_versioning_api

from nominal_checks_from_jama._nominal import (
    ChecklistConflict,
    Keep,
    KeepVariable,
    NewCheck,
    NewVariable,
    NominalError,
    Rewrite,
    SdkChecklists,
)

LINEAGE = "5b47e855-f506-54b1-bf6e-ef046c140f0c"


def check(rid: str, *, condition: object = None) -> scout_checks_api.Check:
    return scout_checks_api.Check(
        check_lineage_rid=f"ri.scout.test.check-lineage.{LINEAGE}",
        description="Text.",
        generated_event_type=event.EventType.ERROR,
        priority=scout_api.Priority.P2,
        rid=rid,
        title="WA-REQ-1 Requirement 1",
        condition=condition,  # type: ignore[arg-type]
    )


def series(channel: str) -> scout_checks_api.VariableLocator:
    return scout_checks_api.VariableLocator(
        series=scout_api.ChannelLocator(channel=channel, data_source_ref="default", tags={})
    )


def versioned(
    checks: list[scout_checks_api.Check],
    variables: list[scout_checks_api.ChecklistVariable] | None = None,
    functions: list[Any] | None = None,
) -> scout_checks_api.VersionedChecklist:
    return scout_checks_api.VersionedChecklist(
        rid="ri.scout.test.checklist.1",
        metadata=scout_checks_api.ChecklistMetadata(
            assignee_rid="ri.user.1",
            author_rid="ri.user.1",
            created_at="2026-11-02T00:00:00Z",
            description="",
            is_archived=False,
            is_published=True,
            labels=[],
            properties={},
            title="Widget Assembly requirements",
        ),
        commit=scout_versioning_api.Commit(
            committed_at="2026-11-02T00:00:00Z",
            committed_by="ri.user.1",
            id="commit-1",
            is_working_state=False,
            message="",
            resource_rid="ri.scout.test.checklist.1",
        ),
        checks=[scout_checks_api.ChecklistEntry(check=c) for c in checks],
        checklist_variables=variables or [],
        functions=functions,
    )


class Service:
    def __init__(self, reply: scout_checks_api.VersionedChecklist | Exception) -> None:
        self.reply = reply
        self.calls: list[tuple[str, Any]] = []

    def _answer(self, name: str, request: Any) -> scout_checks_api.VersionedChecklist:
        self.calls.append((name, request))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply

    def get(self, auth: str, rid: str) -> scout_checks_api.VersionedChecklist:
        return self._answer("get", rid)

    def create(self, auth: str, request: Any) -> scout_checks_api.VersionedChecklist:
        return self._answer("create", request)

    def commit(self, auth: str, rid: str, request: Any) -> scout_checks_api.VersionedChecklist:
        return self._answer("commit", request)


def connect(service: Service) -> SdkChecklists:
    client = SimpleNamespace(
        _clients=SimpleNamespace(checklist=service, auth_header="Bearer test"),
        get_user=lambda: SimpleNamespace(rid="ri.user.1"),
        _workspace_rid_for_search=lambda workspace: "ri.workspace.1",
        search_checklists=lambda properties: [SimpleNamespace(rid="ri.scout.test.checklist.1")],
        get_checklist=lambda rid: SimpleNamespace(nominal_url=f"https://app.example.test/checklists/{rid}"),
    )
    return SdkChecklists(client)  # type: ignore[arg-type]


def conjure_error(code: str) -> ConjureHTTPError:
    response = requests.Response()
    response.status_code = 409 if code == "CONFLICT" else 403
    response._content = f'{{"errorCode": "{code}", "errorName": "Test:{code}"}}'.encode()
    return ConjureHTTPError(requests.HTTPError(response=response))


def condition(**variables: scout_checks_api.VariableLocator) -> scout_checks_api.CheckCondition:
    return scout_checks_api.CheckCondition(
        num_ranges_v3=scout_checks_api.NumRangesConditionV3(
            function_spec={},
            operator=scout_compute_api.ThresholdOperator.GREATER_THAN,
            ranges=scout_compute_api.RangeSeries(raw=scout_compute_api.Reference(name="failure")),
            threshold=0,
            variables=variables,
        )
    )


def uses(name: str) -> scout_checks_api.VariableLocator:
    return scout_checks_api.VariableLocator(checklist_variable=name)


def test_get_reads_checks_and_bare_lineages() -> None:
    nominal = connect(Service(versioned([check("ri.check.1"), check("ri.check.2", condition=condition())])))
    version = nominal.get("ri.scout.test.checklist.1")
    assert version.commit == "commit-1"
    assert [(c.rid, c.lineage, c.title, c.description, c.priority, c.has_condition) for c in version.checks] == [
        ("ri.check.1", LINEAGE, "WA-REQ-1 Requirement 1", "Text.", "P2", False),
        ("ri.check.2", LINEAGE, "WA-REQ-1 Requirement 1", "Text.", "P2", True),
    ]


def test_variables_are_read_by_channel() -> None:
    variables = [
        scout_checks_api.ChecklistVariable(name="a", value=series("voltage")),
        scout_checks_api.ChecklistVariable(name="d", value=uses("a")),
    ]
    nominal = connect(Service(versioned([check("ri.check.1")], variables)))
    found = {v.name: (v.ref_name, v.channel) for v in nominal.get("ri.x").variables}
    assert found == {"a": ("default", "voltage"), "d": (None, None)}


def ranges_of(*inputs: scout_compute_api.RangeSeries) -> scout_checks_api.CheckCondition:
    return scout_checks_api.CheckCondition(
        num_ranges_v3=scout_checks_api.NumRangesConditionV3(
            function_spec={},
            operator=scout_compute_api.ThresholdOperator.GREATER_THAN,
            ranges=scout_compute_api.RangeSeries(
                intersect_range=scout_compute_api.IntersectRanges(inputs=list(inputs))
            ),
            threshold=0,
            variables={},
        )
    )


def test_the_editors_empty_intersection_is_no_condition() -> None:
    # The app's editor, and the MCP server, save a check with no condition this way.
    raw = scout_compute_api.RangeSeries(raw=scout_compute_api.Reference(name="failure"))
    nominal = connect(
        Service(versioned([check("ri.check.1", condition=ranges_of()), check("ri.check.2", condition=ranges_of(raw))]))
    )
    assert [c.has_condition for c in nominal.get("ri.x").checks] == [False, True]


def test_the_editors_channel_variables_are_read_as_channels() -> None:
    # The app's editor saves a channel variable as a compute node that passes one series through.
    node = scout_checks_api.ComputeNodeWithContext(
        series_node=scout_compute_api.ComputeNode(raw=scout_compute_api.Reference(name="x.untypedSeries.input")),
        context=scout_checks_api.CheckContext(
            variables={
                "runStartTimestamp": scout_checks_api.VariableLocator(
                    timestamp=scout_checks_api.TimestampLocator.RUN_START
                ),
                "x.untypedSeries.input": series("voltage"),
            }
        ),
    )
    variables = [
        scout_checks_api.ChecklistVariable(name="a", value=scout_checks_api.VariableLocator(compute_node=node))
    ]
    found = connect(Service(versioned([check("ri.check.1")], variables))).get("ri.x").variables
    assert [(v.ref_name, v.channel) for v in found] == [("default", "voltage")]


def test_a_condition_the_tool_cant_copy_marks_the_check() -> None:
    unknown = scout_checks_api.CheckCondition(num_ranges=object())  # type: ignore[arg-type]
    nominal = connect(Service(versioned([check("ri.check.1", condition=unknown), check("ri.check.2")])))
    assert [c.copyable for c in nominal.get("ri.x").checks] == [False, True]


def test_rewrite_changes_the_text_and_keeps_the_condition() -> None:
    kept = condition(failure=uses("a"))
    service = Service(versioned([check("ri.check.1", condition=kept)]))
    nominal = connect(service)
    version = nominal.get("ri.scout.test.checklist.1")
    nominal.commit(version, [Rewrite(version.checks[0], "New title", "New text.")], [], "From Jama requirements")
    sent = service.calls[-1][1].checks[0].create_check
    assert (sent.title, sent.description, sent.check_lineage_rid, sent.priority) == (
        "New title",
        "New text.",
        LINEAGE,
        scout_api.Priority.P2,
    )
    assert sent.generated_event_type == event.EventType.ERROR
    assert sent.condition.num_ranges_v3.variables["failure"].checklist_variable == "a"
    assert sent.condition.num_ranges_v3.threshold == 0


def test_rewrite_refuses_a_check_it_cant_copy() -> None:
    unknown = scout_checks_api.CheckCondition(num_ranges=object())  # type: ignore[arg-type]
    service = Service(versioned([check("ri.check.1", condition=unknown)]))
    nominal = connect(service)
    version = nominal.get("ri.scout.test.checklist.1")
    with pytest.raises(NominalError, match="can't copy"):
        nominal.commit(version, [Rewrite(version.checks[0], "New", "New.")], [], "message")


def test_create_sends_checks_without_conditions_and_new_variables() -> None:
    service = Service(versioned([check("ri.check.1")]))
    connect(service).create(
        "Name",
        "About it.",
        {"jama_project": "12"},
        [NewCheck(LINEAGE, "T", "D", "P3")],
        [NewVariable("a", "WA-REQ-1: voltage", "default", "voltage")],
    )
    ((name, request),) = service.calls
    variable = request.checklist_variables[0]
    assert (variable.name, variable.display_name, variable.value.series.data_source_ref) == (
        "a",
        "WA-REQ-1: voltage",
        "default",
    )
    assert variable.value.series.channel == "voltage"
    assert name == "create"
    assert (request.title, request.description, request.properties) == ("Name", "About it.", {"jama_project": "12"})
    assert (request.assignee_rid, request.workspace, request.is_published) == ("ri.user.1", "ri.workspace.1", True)
    created = request.checks[0].create_check
    assert (created.check_lineage_rid, created.title, created.priority, created.condition) == (
        LINEAGE,
        "T",
        scout_api.Priority.P3,
        None,
    )


def test_commit_keeps_checks_by_rid_and_sends_variables_back() -> None:
    node = scout_compute_api.ComputeNode(enum=scout_compute_api.EnumSeries(raw=scout_compute_api.Reference(name="a")))
    variables = [
        scout_checks_api.ChecklistVariable(name="a", value=series("voltage"), display_name="Voltage"),
        scout_checks_api.ChecklistVariable(name="b", value=scout_checks_api.VariableLocator(checklist_variable="a")),
        scout_checks_api.ChecklistVariable(
            name="c",
            value=scout_checks_api.VariableLocator(
                compute_node=scout_checks_api.ComputeNodeWithContext(
                    context=scout_checks_api.CheckContext(variables={"a": series("current")}), series_node=node
                )
            ),
        ),
    ]
    service = Service(versioned([check("ri.check.1")], variables))
    nominal = connect(service)
    version = nominal.get("ri.scout.test.checklist.1")
    nominal.commit(
        version,
        [Keep("ri.check.1"), NewCheck(LINEAGE, "T", "D", "P1")],
        [KeepVariable("a"), KeepVariable("b"), KeepVariable("c"), NewVariable("d", "WA-REQ-1: x", "default", "x")],
        "From Jama requirements: 1 added",
    )
    name, request = service.calls[-1]
    assert name == "commit"
    assert request.latest_commit == "commit-1"
    assert request.commit_message == "From Jama requirements: 1 added"
    assert request.checks[0].check == "ri.check.1"
    assert request.checks[1].create_check.condition is None
    sent = {v.name: v for v in request.checklist_variables}
    assert sent["a"].value.series.channel == "voltage"
    assert sent["a"].display_name == "Voltage"
    assert sent["b"].value.checklist_variable == "a"
    assert sent["c"].value.compute_node.context.variables["a"].series.channel == "current"
    assert sent["d"].value.series.channel == "x"
    assert [v.name for v in request.checklist_variables] == ["a", "b", "c", "d"]


def test_functions_are_refused() -> None:
    nominal = connect(Service(versioned([check("ri.check.1")], functions=[object()])))
    with pytest.raises(NominalError, match="functions"):
        nominal.get("ri.scout.test.checklist.1")


def test_errors() -> None:
    with pytest.raises(ChecklistConflict, match="Run the sync again"):
        connect(Service(conjure_error("CONFLICT"))).get("ri.x")
    with pytest.raises(NominalError, match="Test:PERMISSION_DENIED"):
        connect(Service(conjure_error("PERMISSION_DENIED"))).get("ri.x")


def test_find_and_url() -> None:
    nominal = connect(Service(versioned([])))
    assert nominal.find({"jama_project": "12"}) == ["ri.scout.test.checklist.1"]
    assert nominal.url("ri.x") == "https://app.example.test/checklists/ri.x"
