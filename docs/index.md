# Nominal checks from Jama

{.lead}
Turn the requirements and test cases in a Jama Connect® project into checks in Nominal.
The tool reads from Jama Connect and never writes to it.

```{toctree}
:hidden:
:caption: Quickstart

Quickstart <self>
quickstart/jama-api-key
quickstart/api-keys-setup
```

```{toctree}
:hidden:
:caption: Guides

guides/index
guides/agent
guides/sync
guides/test-cases
guides/switch
guides/channels
guides/python
```

```{toctree}
:hidden:
:caption: Reference

reference/index
reference/cli
reference/files
reference/api
```

## Two ways to build the checklist

The tool's `sync` builds the structure: a check for each requirement, without conditions. A condition is what a check measures, and you choose who drafts them.

```{list-table}
:header-rows: 1
:widths: 16 42 42

* -
  - Your agent drafts the conditions
  - You write the conditions
* - How
  - The tool writes instructions for your agent, which works in Nominal through its MCP server or as Analyst
  - The tool creates the checklist structure, you define each one in Nominal
* - Review
  - You review the agent's draft of each check and condition, then publish it
  - Implement the written requirement as a condition within the template structure
* - Steps
  - **This quickstart**, or [Build checks with your agent](guides/agent.md)
  - [Sync checks with the tool](guides/sync.md)
```

You can switch from one to the other later. Requirements and test cases each get a checklist of their own: this quickstart builds the requirements checklist, and [Test cases](guides/test-cases.md) covers the other.

## Before you start

You need:

- Python 3.11 or later, and git.
- Jama Connect API credentials: a client ID and secret. [Get Jama credentials](quickstart/jama-api-key.md) shows how.
- A Nominal profile. [API keys setup](quickstart/api-keys-setup.md) creates it.
- An agent connected to Nominal, to follow the instructions. [Intro to Nominal MCP](site:/quickstart/mcp/) connects Claude, ChatGPT and other agents.

## Get the tool

Clone the repository and install what it needs:

```sh
git clone https://github.com/nominal-io/nominal-jama-connector
cd nominal-jama-connector
python -m pip install -r requirements.txt
```

The commands below run the tool from this folder. Nothing else needs installing.

:::{dropdown} With uv or just
With [uv](https://docs.astral.sh/uv/), skip the install and start each command with `uv run` instead of `python`:

```sh
uv run nominal-checks-from-jama.py init
```

With [just](https://just.systems/) and uv, `just run` runs the tool from any folder: `just run init`.
:::

## Point it at your Jama project

```sh
python nominal-checks-from-jama.py init
```

`init` asks for:

- Your Jama Connect URL. Open a requirement in your project and copy the URL from your browser's address bar. Any Jama Connect page works, but a requirement's URL also gives `init` the project id.
- The project id. `init` offers the one in the URL you pasted: press Enter to keep it. Otherwise, open the project in Jama Connect. Look for `projectId=<id>` or `/projects/<id>/` in the URL, depending on the page.
- Your API client ID and secret, from [Get Jama credentials](quickstart/jama-api-key.md).

`init` stores the secret on your computer, in your operating system's credential manager, under the name `nominal-checks-from-jama:` followed by your Jama Connect URL.
The secret isn't written to any file. To remove it, delete that entry in the credential manager.

`init` then writes `jama-checks.toml` with the project's requirement and test case item types filled in:

```text
Stored the secret in your operating system's credential manager.
Connecting to https://example.jamacloud.com to read project 12's item types...
Project 12: Widget Assembly
Reading 1 requirement type, 2 items, for the requirements checklist:
  34 Requirement (2 items)
Reading 1 test case type, 1 item, for a separate test cases checklist:
  35 Test Case (1 item)
Not reading:
  6 types with no items in this project
  3 container types, which hold other items: Set, Folder, Text
Wrote jama-checks.toml. Check [jama] item_types and test_case_types, then run `nominal-checks-from-jama agent-plan`.
```

If a type under **Not reading** holds requirements, add its id to `item_types` in `jama-checks.toml`. If it holds test cases, add it to `test_case_types`.

## Create the checks

Nominal's tools for agents save a new check only with a condition, so `sync` creates the checks first, without conditions:

```sh
python nominal-checks-from-jama.py sync
```

```text
  created: WA-REQ-101 Brake temperature
  created: WA-REQ-102 Pedal force
Created the checklist: 2 created.
https://app.gov.nominal.io/w/<workspace>/checklists/<checklist RID>
```

`sync` publishes the checklist, named `<Jama project name> requirements`. Your agent adds the conditions in a draft of it.

## Write your agent's instructions

`agent-plan` writes `checks-plan.md`: the steps your agent follows, then the exact title and description for each requirement's check.
Pass the run or asset whose channels the conditions should use:

```sh
python nominal-checks-from-jama.py agent-plan --target <run or asset RID>
```

```text
Wrote checks-plan.md: 2 requirements.
Give it to your agent connected to Nominal, then review its draft before publishing.
```

Without `--target`, the instructions tell the agent to ask you which run or asset to use, and your agent can find it by name.
If you have no data yet, the agent proposes a channel name from each requirement's wording, such as `ground_speed`. Once you have data, your agent [matches them to your channels](guides/agent.md#match-proposed-channels-to-your-data).

## Give the instructions to your agent

Start your agent in the folder with `checks-plan.md`, and ask:

```text
Follow the instructions in checks-plan.md.
```

The agent finds the checklist `sync` made, and drafts a condition for each requirement it can measure on a channel of the run or asset, in a draft of the checklist.
It doesn't publish. When it's done, it links the draft and lists each requirement it left without a condition, with the reason.
It also lists the channel each condition reads, and the channel names it proposed because no data matched.
To review and publish the draft, see [Build checks with your agent](guides/agent.md#review-and-publish-the-draft).

## Write the instructions from Python

The same, from a script. Install the package from the cloned folder first, with `python -m pip install .`:

```python
from nominal_checks_from_jama import Config, checks_from_jama, write_agent_plan

config = Config.load("jama-checks.toml")
checks = checks_from_jama(config)  # read the requirements, and make a check for each
plan = write_agent_plan(checks, target="<run or asset RID>")
with open("checks-plan.md", "w", encoding="utf-8") as file:
    file.write(plan.markdown)
```

[Use the tool from Python](guides/python.md) covers each step.

Jama Connect® is a registered trademark of Jama Software, Inc.
