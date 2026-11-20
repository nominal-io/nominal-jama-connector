# Build a Nominal checklist from Jama requirements

You can work in Nominal, through its MCP server or as Nominal's Analyst. Below are requirements from the Jama Connect project 12 (Widget Assembly), each with the exact title and description its check in Nominal should have. Draft a condition for each requirement that states something you can measure, on the requirement's check in the checklist.

## Tools

These are the Nominal MCP server's tools the steps use, as named when these instructions were written. If a tool has another name now, works differently, or you're Analyst and your tools have other names, use whichever tool does what the second column says.

| Tool | What these instructions use it for |
| --- | --- |
| `search_checklists` | Find the checklist for this Jama project, by its properties. |
| `create_checklist` | Create the checklist when there is none. |
| `update_checklist` | Set the checklist's properties, so later runs find it. |
| `get_checklist` | List the checklist's checks and drafts. |
| `get_checklist_document` | Read the checks' titles, descriptions and conditions before editing. |
| `update_checklist_document` | Add checks and conditions, saved to a draft (or main while unpublished). |
| `validate_checklist_document` | Test a large edit before saving it. |
| `search_runs`, `search_assets` | Find the run or asset whose channels the conditions use. |
| `search_channels` | Find exact channel names, with their values, before writing a condition. |
| `describe_formula` | Look up the condition functions and their arguments. |

## Steps

1. Find the checklist: search for checklists with the properties `jama_host` = `example.jamacloud.com`, `jama_project` = `12`, `jama_items` = `requirements`. If there's none, create one named `Widget Assembly requirements`, then set those properties on it so later runs find it. If there's more than one, stop and ask the user which to use.
2. Edit a draft of the checklist, never its published version. While a new checklist is unpublished, edit it directly. Don't publish: the user reviews your draft in Nominal and publishes it.
3. Find each requirement's check by the line in its description that starts with `Jama:` and links to the requirement. Nominal saves a new check only with a condition. The tool's `sync` command makes each item's check without a condition, so if it has run, every item already has its check for you to add conditions to.
4. Draft a condition for each requirement that states a limit or behavior you can measure; a check fails where its condition holds. Add the condition to the requirement's check. If the requirement has no check, add one with exactly the title and description given below, including that last line, and the condition: later runs find the check by that line. If the requirement states nothing measurable, add no condition, and if it has no check, don't add one. Use each threshold as stated. When the value itself should make the condition hold, use `greaterThanEqual` or `lessThanEqual` rather than shifting the threshold. For example, a requirement to stay below 450 fails at 450 too, so its condition is `greaterThanEqual` 450. Prefer conditions on channels the system outputs over a proposed channel the user would have to compute from other data. For example, where a requirement says Y must follow X within a time T, and X and Y are channels you found or proposed, don't propose a channel for the delay between them. Write a condition that holds while X has happened and Y hasn't, and set the check's time persistence (`timePersistence`) to T, so the check fails only when that state lasts past T. This works only while X stays set until Y happens, such as an alarm that latches or a command that's held. If you can't tell, or X is a brief event in the data, say so in the report. Where a requirement states a statistic over many samples, such as a mean or a percentile, don't replace it with a limit on each sample: leave it without a condition and give the reason.
5. Choose each condition's channel this way. If the requirement marks channels, use those names. Otherwise search the channels of the asset or run `ri.scout.example.run.1` for one that measures what the requirement states, and use it. If none matches, or there's no run or asset with data yet, propose a channel name from the requirement's wording: lower case, words joined by underscores, naming the measurement, such as `ground_speed`, in the data scope `default`. Nominal saves a condition on a channel no data has yet, but rejects it when the edit gives channelSource, which makes it look up every condition's channel. So save conditions on channels the run or asset has with channelSource, and conditions on other channels in a separate edit without it.
6. If the run or asset has data, also look at the conditions already on these checks. Where one reads a channel the run or asset doesn't have, such as a name proposed earlier, find its channel that measures the same thing, and change the condition to read it. Where the units differ, convert the threshold. Change nothing else in the condition, and leave a channel you can't match as it is.
7. Leave every check's title and description as they are, and don't delete checks, including checks that link to a requirement not listed below. Comparing the checks' text with Jama, and finding checks for items gone from Jama, is the tool's `sync` command's job, so don't compare them yourself.
8. Don't change a condition someone else wrote, except its channel as step 6 says.
9. When you're done, link the draft, and report: the checks you added, the conditions you drafted with the channel each reads and why you chose it (marked, matched from the requirement's wording, or proposed), and each requirement you left without a condition or without a check, with the reason. Also list each condition whose channel you changed, from which channel to which, and each channel you couldn't match. List every channel name you proposed, however many there are, each with its check and data scope. Don't send the user to the draft for them. Until a run has those channels, the checklist won't execute on it. Tell the user that once a run or asset has data, they can write these instructions again with it as the target, and an agent following them changes the proposed channels to the ones it has. If any item has no check because you couldn't draft a condition for it, tell the user that the tool's `sync` command creates the missing checks without conditions, and that they can give you these instructions again afterwards.

## Requirements (2)

### WA-REQ-101 Brake temperature

- Jama: https://example.jamacloud.com/perspective.req#/items/101?projectId=12
- Channels the requirement marks: `brake_temp`

Title:

```text
WA-REQ-101 Brake temperature
```

Description:

```text
`brake_temp` stays below 450°C during a "hot stop"; no fade.

Jama: https://example.jamacloud.com/perspective.req#/items/101?projectId=12
```

### WA-REQ-102 Pedal force

- Jama: https://example.jamacloud.com/perspective.req#/items/102?projectId=12

Title:

```text
WA-REQ-102 Pedal force
```

Description:

```text
Under 500 N at full braking.

Jama: https://example.jamacloud.com/perspective.req#/items/102?projectId=12
```
