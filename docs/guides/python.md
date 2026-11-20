# Use the tool from Python

{.lead}
Each step is a function that takes the previous step's data and returns its own, so your code can run, replace or add to any of them.
Install the package to import it:

```sh
python -m pip install git+https://github.com/nominal-io/nominal-jama-connector
```

Installing also adds the `nominal-checks-from-jama` command. If your shell doesn't find it, use `python -m nominal_checks_from_jama` in its place.

## The steps

| Step | Function | Returns | Its file |
| --- | --- | --- | --- |
| 1. Read the requirements | `read_requirements(config)` | `Requirements` | `requirements.json` |
| 2. Make a check for each | `build_checks(requirements)` | `Checks` | `checks.json` |
| 3a. Write your agent's plan | `write_agent_plan(checks)` | `AgentPlan` | `checks-plan.md` |
| 3b. Keep the checklist in Nominal | `sync(checks)` | `SyncResult` | |

`checks_from_jama(config)` runs steps 1 and 2 together.
`Requirements` and `Checks` each have `save` and `load` for their file, so you can run a step, change its file, and start the next step from it.

## Write the plan

```python
from nominal_checks_from_jama import Config, build_checks, read_requirements, write_agent_plan

config = Config.load("jama-checks.toml")
requirements = read_requirements(config)
checks = build_checks(requirements, markers=config.nominal.channel_markers)
plan = write_agent_plan(checks, target="<run or asset RID>")
with open("checks-plan.md", "w", encoding="utf-8") as file:
    file.write(plan.markdown)
```

## Sync the checklist

```python
from nominal_checks_from_jama import Config, Field, checks_from_jama, sync

config = Config.load("jama-checks.toml")
result = sync(checks_from_jama(config), nominal=config.nominal, update=[Field.TITLE])
for item in result.plan.results:
    print(item.outcome, item.title)
    for difference in item.differences:
        print("  ", difference.field, repr(difference.nominal), "->", repr(difference.jama))
print(result.checklist_url)
```

`plan_sync` works out the same changes without connecting to Nominal, from a checklist version you pass it.

## Change a step

To change which channels become variables, pass your own function to `build_checks`, as in [Mark channels in requirements](channels.md#find-channels-your-own-way).
To change anything else, change the `Checks` before passing it on. `Checks` and `CheckSpec` are frozen dataclasses, so use `dataclasses.replace`. This leaves out requirements with no text:

```python
from dataclasses import replace

from nominal_checks_from_jama.checks import JAMA_LINK

checks = replace(checks, checks=tuple(c for c in checks.checks if not c.description.startswith(JAMA_LINK)))
```

Keep each description's last line, the link to Jama Connect: both outputs find a requirement's check by it.

[Python API](../reference/api.md) documents every function and class.

Jama Connect® is a registered trademark of Jama Software, Inc.
