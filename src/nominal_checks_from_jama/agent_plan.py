"""Output: instructions for an agent to build and keep the checklist. Its file is ``checks-plan.md``,
or ``test-checks-plan.md`` for test cases.

The tool calls no model, and needs neither Jama nor Nominal for this step: it writes Markdown from
the checks, which a person gives to their own agent, such as Claude, ChatGPT or Nominal's Analyst,
connected to Nominal. The agent creates or finds the checklist, drafts conditions where a
requirement or a test case's pass criterion is measurable, and leaves publishing to a person.

Nominal's tools for agents save a new check only with a condition, so the agent adds a check only
together with its condition. Running ``sync`` first gives every item a check without a condition,
for the agent to add conditions to; without it, the agent reports the items it couldn't add.

The agent finds each item's check by the line in its description that links to Jama, and leaves
the checks' text alone: ``sync`` compares it with Jama and reports what differs and what's gone.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from nominal_checks_from_jama.checks import JAMA_LINK, Checks, CheckSpec
from nominal_checks_from_jama.kinds import ItemKind
from nominal_checks_from_jama.nominal_sync import checklist_name as name_checklist
from nominal_checks_from_jama.nominal_sync import checklist_properties

# The Nominal MCP server's tools at the time of writing, and what the instructions use each for. If
# one is renamed or behaves differently, the agent can still tell what each step needs.
TOOLS: Sequence[tuple[str, str]] = (
    ("search_checklists", "Find the checklist for this Jama project, by its properties."),
    ("create_checklist", "Create the checklist when there is none."),
    ("update_checklist", "Set the checklist's properties, so later runs find it."),
    ("get_checklist", "List the checklist's checks and drafts."),
    ("get_checklist_document", "Read the checks' titles, descriptions and conditions before editing."),
    ("update_checklist_document", "Add checks and conditions, saved to a draft (or main while unpublished)."),
    ("validate_checklist_document", "Test a large edit before saving it."),
    ("search_runs, search_assets", "Find the run or asset whose channels the conditions use."),
    ("search_channels", "Find exact channel names, with their values, before writing a condition."),
    ("describe_formula", "Look up the condition functions and their arguments."),
)


@dataclass(frozen=True)
class AgentPlan:
    """The instructions, and what they cover.

    Attributes:
        markdown (str): The file's contents.
        checks (tuple[str, ...]): The titles of the checks they cover.
    """

    markdown: str
    checks: tuple[str, ...]


def _names(tools: str) -> str:
    """Tool names separated by commas, each in its own code span."""
    return ", ".join(f"`{name}`" for name in tools.split(", "))


def _fence(text: str) -> str:
    """Text in a fenced block long enough that no backticks inside it can close it early."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}text\n{text}\n{fence}"


def _block(check: CheckSpec, kind: ItemKind) -> str:
    lines = [f"### {check.title}", "", f"- Jama: {check.url}"]
    if check.channels:
        lines.append(f"- Channels the {kind.singular} marks: " + ", ".join(f"`{name}`" for name in check.channels))
    lines += ["", "Title:", "", _fence(check.title), "", "Description:", "", _fence(check.description)]
    return "\n".join(lines)


# Opens every plan: the same instructions work for an agent on the MCP server and for Analyst.
_WHO = "You can work in Nominal, through its MCP server or as Nominal's Analyst."


def _intro(kind: ItemKind, project: str, project_name: str) -> str:
    where = f"the Jama Connect project {project} ({project_name})"
    if kind is ItemKind.TEST_CASES:
        return (
            f"{_WHO} Below are test cases from {where}, each with the title and description its checks in "
            "Nominal should have. A description holds the test case's procedure and pass criteria. Give each "
            "test case as many checks as its pass criteria need, each with a condition for the criterion it "
            "covers where you can measure it."
        )
    return (
        f"{_WHO} Below are requirements from {where}, each with the exact title and description its check in "
        "Nominal should have. Draft a condition for each requirement that states something you can measure, on "
        "the requirement's check in the checklist."
    )


# Said in each kind's steps: why the agent can't always add a check, and where the missing ones come from.
_NEEDS_CONDITION = (
    "Nominal saves a new check only with a condition. The tool's `sync` command makes each item's check without "
    "a condition, so if it has run, every item already has its check for you to add conditions to."
)
# The tool compares exactly and every time; an agent may skip the comparison on a long checklist.
_SYNC_COMPARES = (
    "Comparing the checks' text with Jama, and finding checks for items gone from Jama, is the tool's `sync` "
    "command's job, so don't compare them yourself."
)
_SYNC_TIP = (
    "If any item has no check because you couldn't draft a condition for it, tell the user that the tool's "
    "`sync` command creates the missing checks without conditions, and that they can give you these "
    "instructions again afterwards."
)


def _channels(number: int, where: str, data_scope: str, item: str) -> str:
    """The step that says how to choose each condition's channel, and how to save one the data doesn't have."""
    return (
        f"{number}. Choose each condition's channel this way. If the {item} marks channels, use those names. "
        f"Otherwise search the channels of {where} for one that measures what the {item} states, and use it. "
        f"If none matches, or there's no run or asset with data yet, propose a channel name from the {item}'s "
        "wording: lower case, words joined by underscores, naming the measurement, such as `ground_speed`, in "
        f"the data scope `{data_scope}`. Nominal saves a condition on a channel no data has yet, but rejects it "
        "when the edit gives channelSource, which makes it look up every condition's channel. So save "
        "conditions on channels the run or asset has with channelSource, and conditions on other channels in "
        "a separate edit without it."
    )


def _match(number: int) -> str:
    """The step that moves existing conditions, such as ones on proposed channels, onto the data's channels."""
    return (
        f"{number}. If the run or asset has data, also look at the conditions already on these checks. Where one "
        "reads a channel the run or asset doesn't have, such as a name proposed earlier, find its channel that "
        "measures the same thing, and change the condition to read it. Where the units differ, convert the "
        "threshold. Change nothing else in the condition, and leave a channel you can't match as it is."
    )


# Said in each kind's drafting step: Nominal has or-equal comparisons, so thresholds stay as stated.
_EXACT = (
    "Use each threshold as stated. When the value itself should make the condition hold, use `greaterThanEqual` "
    "or `lessThanEqual` rather than shifting the threshold. For example, a requirement to stay below 450 fails "
    "at 450 too, so its condition is `greaterThanEqual` 450."
)

# Said in each kind's drafting step: a proposed channel someone would have to compute is a last resort. The
# example is generic on purpose, so it doesn't hand the agent the answer for a real requirement.
_COMPUTED = (
    "Prefer conditions on channels the system outputs over a proposed channel the user would have to compute "
    "from other data. For example, where a requirement says Y must follow X within a time T, and X and Y are "
    "channels you found or proposed, don't propose a channel for the delay between them. Write a condition that "
    "holds while X has happened and Y hasn't, and set the check's time persistence (`timePersistence`) to T, so "
    "the check fails only when that state lasts past T. This works only while X stays set until Y happens, such "
    "as an alarm that latches or a command that's held. If you can't tell, or X is a brief event in the data, "
    "say so in the report. Where a requirement states a statistic over many "
    "samples, such as a mean or a percentile, don't replace it with a limit on each sample: leave it without a "
    "condition and give the reason."
)

_PROPOSED = (
    "List every channel name you proposed, however many there are, each with its check and data scope. Don't "
    "send the user to the draft for them. Until a run has those channels, the checklist won't execute on it. "
    "Tell the user that once a run or asset has data, they can write these instructions again with it as the "
    "target, and an agent following them changes the proposed channels to the ones it has."
)
_MATCHED = (
    "Also list each condition whose channel you changed, from which channel to which, and each channel you "
    "couldn't match."
)


def _requirement_steps(where: str, data_scope: str) -> list[str]:
    return [
        f"3. Find each requirement's check by the line in its description that starts with `{JAMA_LINK.strip()}` "
        f"and links to the requirement. {_NEEDS_CONDITION}",
        "4. Draft a condition for each requirement that states a limit or behavior you can measure; a check "
        "fails where its condition holds. Add the condition to the requirement's check. If the requirement has "
        "no check, add one with exactly the title and description given below, including that last line, and "
        "the condition: later runs find the check by that line. If the requirement states nothing measurable, "
        f"add no condition, and if it has no check, don't add one. {_EXACT} {_COMPUTED}",
        _channels(5, where, data_scope, "requirement"),
        _match(6),
        "7. Leave every check's title and description as they are, and don't delete checks, including checks "
        f"that link to a requirement not listed below. {_SYNC_COMPARES}",
        "8. Don't change a condition someone else wrote, except its channel as step 6 says.",
        "9. When you're done, link the draft, and report: the checks you added, the conditions you drafted with "
        "the channel each reads and why you chose it (marked, matched from the requirement's wording, or "
        "proposed), and each requirement you left without a condition or without a check, with the reason. "
        f"{_MATCHED} {_PROPOSED} {_SYNC_TIP}",
    ]


def _test_case_steps(where: str, data_scope: str) -> list[str]:
    link = JAMA_LINK.strip()
    return [
        f"3. Find each test case's checks by the line in their descriptions that starts with `{link}` and "
        f"links to the test case. A test case can have more than one check. {_NEEDS_CONDITION}",
        "4. Make an appropriate number of checks to satisfy each test case's pass criteria: one check for each "
        "criterion you can verify on its own, or a single check when it has one criterion or its criteria can't "
        "be separated. Give every check exactly the description given below, including its last line, "
        f"`{link}` and the link: later runs find the checks by it. A single check has exactly the title given "
        "below. When there's more than one, title each with that title, then `: `, then a few words naming the "
        "criterion it covers. A test case that already has one check without a condition can keep it for one "
        "criterion, retitled that way, with a new check for each other criterion.",
        "5. For each check, draft a condition for the criterion it covers; a check fails where its condition "
        "holds. Add a new check only together with its condition. If a criterion isn't measurable, add no "
        f"condition for it, and no check for it unless the test case's existing check covers it. {_EXACT} "
        f"{_COMPUTED}",
        _channels(6, where, data_scope, "test case"),
        _match(7),
        "8. Leave every check's description as it is, and its title too except as step 4 says, and don't delete "
        f"checks, including checks that link to a test case not listed below. {_SYNC_COMPARES}",
        "9. Don't change a condition someone else wrote, except its channel as step 7 says.",
        "10. When you're done, link the draft, and report: the checks you added, with how many you made for "
        "each test case and why, the conditions you drafted with the channel each reads and why you chose it "
        "(marked, matched from the test case's wording, or proposed), and each criterion you left without a "
        f"condition or without a check, with the reason. {_MATCHED} {_PROPOSED} {_SYNC_TIP}",
    ]


def write_agent_plan(
    checks: Checks,
    *,
    target: str | None = None,
    checklist_name: str = "",
    data_scope: str = "default",
) -> AgentPlan:
    """Write the instructions for an agent from the checks.

    Args:
        checks (Checks): The checks, from step 2.
        target (str | None): The RID of an asset or run whose channels the conditions should use.
            When None, the instructions tell the agent to ask, and to propose channel names if the
            user has no data yet.
        checklist_name (str): The checklist's name, if the agent creates it; ``<project name>
            requirements`` or ``<project name> test cases`` when empty.
        data_scope (str): The data scope for channels the agent proposes, which the user's runs
            should use: ``[nominal] ref_name`` in the settings.

    Returns:
        AgentPlan: The instructions.
    """
    source, kind = checks.source, checks.kind
    name = name_checklist(source, kind, checklist_name)
    properties = checklist_properties(source, kind)
    shown = ", ".join(f"`{key}` = `{value}`" for key, value in properties.items())
    where = (
        f"the asset or run `{target}`"
        if target
        else "the asset or run the user names (ask them which; they may have none yet)"
    )
    tools = ["| Tool | What these instructions use it for |", "| --- | --- |"]
    tools += [f"| {_names(tool)} | {intent} |" for tool, intent in TOOLS]
    find = (
        f"1. Find the checklist: search for checklists with the properties {shown}. If there's none, create "
        f"one named `{name}`, then set those properties on it so later runs find it. If there's more than one, "
        "stop and ask the user which to use."
    )
    draft = (
        "2. Edit a draft of the checklist, never its published version. While a new checklist is unpublished, "
        "edit it directly. Don't publish: the user reviews your draft in Nominal and publishes it."
    )
    steps = (_test_case_steps if kind is ItemKind.TEST_CASES else _requirement_steps)(where, data_scope)
    header = [
        f"# Build a Nominal checklist from Jama {kind.plural}",
        "",
        _intro(kind, source.project, source.project_name),
        "",
        "## Tools",
        "",
        "These are the Nominal MCP server's tools the steps use, as named when these instructions were written. "
        "If a tool has another name now, works differently, or you're Analyst and your tools have other names, "
        "use whichever tool does what the second column says.",
        "",
        *tools,
        "",
        "## Steps",
        "",
        find,
        draft,
        *steps,
        "",
        f"## {kind.plural.capitalize()} ({len(checks.checks)})",
    ]
    blocks = [_block(check, kind) for check in checks.checks]
    body = "\n\n".join(blocks) if blocks else f"There are no {kind.plural}."
    return AgentPlan(
        markdown="\n".join(header) + "\n\n" + body + "\n",
        checks=tuple(check.title for check in checks.checks),
    )
