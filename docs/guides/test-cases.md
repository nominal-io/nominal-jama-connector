# Test cases

{.lead}
Test cases get a Nominal checklist of their own, apart from the requirements checklist, so the people who keep each one don't share it.
Every command works on test cases when you add `--test-cases`.

`init` fills in `test_case_types` in `jama-checks.toml` with the item types Jama Connect marks as test cases.
If one is missing, add its id there.
To read the item types again with the settings you have, such as after a type is added in Jama Connect, run `python nominal-checks-from-jama.py init --re-init`.

## With your agent

```sh
python nominal-checks-from-jama.py agent-plan --test-cases --target <run or asset RID>
```

This writes `test-checks-plan.md`. Give it to your agent as in [Give the instructions to your agent](../index.md#give-the-instructions-to-your-agent), naming that file.

The agent makes as many checks for each test case as its pass criteria need: one per criterion it can verify on its own, or one for the whole test case.
It adds a check only together with its condition, so run `sync --test-cases` first to give every test case a check, as in [Create the checks first](agent.md#create-the-checks-first).
Every check keeps the test case's description and its link to Jama Connect.
When the agent splits a test case, each check's title is the test case's title, then the criterion it covers, such as `WA-TC-201 Hot stop test: peak temperature`.

## With the tool

```sh
python nominal-checks-from-jama.py sync --test-cases
```

`sync` keeps one check per test case, in a checklist named `<project name> test cases`.
If your agent split a test case into several checks, `sync` leaves them as they are and lists them.
[Sync checks with the tool](sync.md) covers the rest, the same for both checklists.

## What a test case's check holds

The check's description is the test case's description, then its steps when the test case uses the **Steps** field, then the line linking to Jama Connect:

```text
Verify the brake temperature during a hot stop.

Steps:
1. Action: Heat the rotor to 300 °C.
   Expected result: `brake_temp` reads 300 ± 5 °C.
2. Action: Release the brake.
   Expected result: `brake_temp` stays below 450 °C.

Jama: https://example.jamacloud.com/perspective.req#/items/201?projectId=12
```

Test cases that keep their procedure and pass criteria in the description need nothing more.

## Files

| Step | Requirements | Test cases |
| --- | --- | --- |
| `read` | `requirements.json` | `test-cases.json` |
| `checks` | `checks.json` | `test-checks.json` |
| `agent-plan` | `checks-plan.md` | `test-checks-plan.md` |

A command started from a test cases file with `--from` needs `--test-cases` too.

Jama Connect® is a registered trademark of Jama Software, Inc.
