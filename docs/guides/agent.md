# Build checks with your agent

{.lead}
`agent-plan` writes `checks-plan.md`, instructions for your agent to keep a Nominal checklist with a check per requirement and to draft the conditions.
The agent works through [Nominal's MCP server](site:/quickstart/mcp/) in a draft of the checklist, and you publish it.

The tool calls no model, and the agent's conditions are drafts. Review each one before you publish.

## Create the checks first

Nominal's tools for agents save a new check only with a condition, so on its own your agent adds a check only for a requirement it can write a condition for.
Run `sync` first to create a check, without a condition, for every requirement:

```sh
python nominal-checks-from-jama.py sync
```

Your agent then adds conditions to those checks. [Sync checks with the tool](sync.md) covers `sync`.

## Write the plan

Pass the run or asset whose channels the conditions should use:

```sh
python nominal-checks-from-jama.py agent-plan --target <run or asset RID>
```

Without `--target`, the plan tells the agent to ask you which run or asset to use.

For each condition, the agent uses the channel the requirement marks, or else looks for a channel on the run or asset that measures what the requirement states.
If none matches, or you have no data yet, it proposes a channel name from the requirement's wording, such as `ground_speed`, in the data scope `ref_name` names in `jama-checks.toml` (`default` unless you set it).
Once you have data, your agent [matches the proposed channels to it](#match-proposed-channels-to-your-data).

To write the plan from a file instead of reading Jama, pass it with `--from`: a `requirements.json` or `checks.json` the tool or your own code wrote. [Files](../reference/files.md) describes both.

Each requirement in `checks-plan.md` has the exact title and description its check should have, its Jama Connect link, and the channels it [marks](channels.md).
The plan also lists the Nominal tools it expects the agent to use, with what each is for, so the agent can adapt if a tool has changed.

## Run your agent

Start your agent in the folder with `checks-plan.md`, and ask:

```text
Follow the instructions in checks-plan.md.
```

To use Nominal's Analyst instead, open Analyst and paste the contents of `checks-plan.md` into it.

The agent:

1. Finds the checklist for the Jama Connect project by its properties, `jama_host`, `jama_project` and `jama_items`, or creates one and sets them.
2. Drafts a condition, in a draft of the checklist, where a requirement states a limit or behavior it can measure on a channel of the run or asset. It adds the condition to the requirement's check, or adds the check with it. In the check's description, after the line that links to Jama Connect, it notes what the condition assumes, such as how it defined a phase of operation.
3. Where the run or asset has data, moves each existing condition on a channel it lacks, such as a proposed name, to the channel that measures the same thing.
4. Links the draft, and lists the channel each condition reads and why it chose it, the channel names it proposed, and each requirement it left without a condition or a check, with the reason.

Where the agent found a requirement ambiguous, fix its wording in Jama Connect, then write the plan again.

## Review and publish the draft

1. Open the checklist and click **EDIT CHECKLIST**.
2. Under **Edit existing draft**, select the agent's draft, and click **EDIT DRAFT**.
3. Check each condition against its requirement and the agent's notes: the channel, the threshold and its units, and that the condition describes the failure. For "stays below 450 °C", the condition is `brake_temp` ≥ 450.
4. Fix or remove any condition that's wrong.
5. Click **PUBLISH**, choose **Publish as latest version…**, enter a **Message**, and click **PUBLISH**.

% SCREENSHOT: the agent's draft open in the checklist editor, with a drafted condition

## Match proposed channels to your data

Your agent can't execute the checklist on a run that lacks one of its channels.
Once a run has data, write the plan again with that run as the target, and give it to your agent:

```sh
python nominal-checks-from-jama.py agent-plan --target <run RID>
```

The agent moves each condition on a channel the run lacks, such as a proposed name, to the run's channel that measures the same thing, and converts the threshold where the units differ.
It lists each channel it changed, and each it couldn't match. Review and publish the draft as above.

## Run the checklist on a run

Open the run's **Checklist executions** tab and click **EXECUTE CHECKLIST**.
Checks without a condition are left out of the result.
[Workbooks: Checklists](site:/platform/workbooks/#checklists) explains checklists and checks.

## Keep the checklist in line with Jama

When requirements change in Jama Connect, run `sync`.
It adds checks for new requirements, rewrites the title and description of each check whose requirement changed, keeping its condition and notes, and lists the checks whose requirement is gone.
[Sync again after Jama changes](sync.md#sync-again-after-jama-changes) covers its options.
Then write the plan again and give it to your agent, which drafts conditions for the new checks.

Jama Connect is the source of truth for each check's title, and its description up to the line that links to Jama Connect. Your agent leaves those alone.
Add your own notes after that line: `sync` keeps them.
Where `sync` says it can't copy a check's condition, it can't rewrite that check's text either: ask your agent to change it, or edit it in Nominal.

Jama Connect® is a registered trademark of Jama Software, Inc.
