# Files

## Settings file

`init` writes the settings to `jama-checks.toml`.
The other commands read it from the current folder, or from the file `--config` names. `agent-plan` and `sync` with `--from` work without it, using the defaults below.
Ids can be written as numbers or strings.

### `[jama]`

| Key | Default | Meaning |
|---|---|---|
| `base_url` | required | Your Jama Connect URL, such as `https://example.jamacloud.com`. A page's URL works too: the tool uses the part before `/perspective.req`. |
| `project` | required | The project id. |
| `item_types` | `[]` | The ids of the item types whose items are requirements. `init` fills it in. |
| `test_case_types` | `[]` | The ids of the item types whose items are test cases, for commands run with `--test-cases`. `init` fills it in with the types Jama Connect marks as test cases. |
| `auth` | `"client_credentials"` | How to sign in: `"client_credentials"` (an API client ID and secret), `"basic"` (a username and password, which instances with single sign-on refuse) or `"token"` (an access token, which nothing renews). |
| `account` | `""` | The API client ID, or the username for `"basic"`. The secret is kept in your operating system's credential manager under this name and the Jama Connect URL. `login` stores it. |

### `[nominal]`

| Key | Default | Meaning |
|---|---|---|
| `profile` | `"default"` | The profile in the Nominal config file to connect with. |
| `checklist_name` | `<project name> requirements` | The requirements checklist's name, when `sync` or your agent creates it. |
| `test_case_checklist_name` | `<project name> test cases` | The test cases checklist's name, when `sync` or your agent creates it. |
| `priority` | `"P3"` | The priority of checks `sync` creates, `"P0"` to `"P4"`. |
| `ref_name` | `"default"` | The data source that variables for marked channels read. |
| `channel_markers` | `[]` | Pairs that mark a channel besides backticks and code formatting: any of `"{}"`, `"[]"` and `"<>"`. |

## Requirements file

`read` writes `requirements.json`: what Jama Connect has for each requirement.
`read --test-cases` writes the same layout to `test-cases.json`, for test cases.
`checks`, `agent-plan` and `sync` start from either with `--from`.

```json
{
  "format": "nominal-checks-from-jama/requirements",
  "version": 1,
  "items": "requirements",
  "source": {"base_url": "https://example.jamacloud.com", "project": "12", "project_name": "Widget Assembly"},
  "requirements": [
    {
      "item_id": "101",
      "document_key": "WA-REQ-101",
      "name": "Brake temperature",
      "text": "`brake_temp` stays below 450°C during a hot stop.",
      "html": "<p>`brake_temp` stays below 450&deg;C during a hot stop.</p>",
      "url": "https://example.jamacloud.com/perspective.req#/items/101?projectId=12"
    }
  ]
}
```

| Key | Meaning |
|---|---|
| `format`, `version` | The kind of file and its layout's version. The tool refuses a file with another. |
| `items` | `"requirements"` or `"test_cases"`. A command given a test cases file needs `--test-cases`. |
| `source` | The Jama Connect instance, the project id and the project's name. |
| `text` | The item's description as plain text. A test case's steps follow it, each with its action, expected result and notes. |
| `html` | The same, as HTML. |

## Checks file

`checks` writes `checks.json`: the check for each requirement. `checks --test-cases` writes `test-checks.json`, one check per test case. `agent-plan` and `sync` start from either with `--from`, and read nothing else, so your own code can write it.

```json
{
  "format": "nominal-checks-from-jama/checks",
  "version": 1,
  "items": "requirements",
  "source": {"base_url": "https://example.jamacloud.com", "project": "12", "project_name": "Widget Assembly"},
  "checks": [
    {
      "item_id": "101",
      "document_key": "WA-REQ-101",
      "url": "https://example.jamacloud.com/perspective.req#/items/101?projectId=12",
      "lineage": "bdd8e896-e600-54fd-bcba-02b4df5bbc5e",
      "title": "WA-REQ-101 Brake temperature",
      "description": "`brake_temp` stays below 450°C during a hot stop.\n\nJama: https://example.jamacloud.com/perspective.req#/items/101?projectId=12",
      "channels": ["brake_temp"]
    }
  ]
}
```

| Key | Meaning |
|---|---|
| `lineage` | The check's lineage in Nominal: the same for a requirement on every run. `sync` sets it on the checks it creates and finds them by it. |
| `title`, `description` | The check's text. The description's last line links to the requirement; both outputs find a requirement's check by it. |
| `channels` | The channel names to make checklist variables for. |

Both files are JSON, so any quote, semicolon or line break in a requirement's text is kept exactly.

## Plan file

`agent-plan` writes `checks-plan.md`, Markdown for your agent: a table of the Nominal tools it uses and what each is for, the steps to follow, and each requirement's exact title and description.
It's written from `checks.json`, so `agent-plan --from checks.json` needs neither Jama Connect nor Nominal.
`agent-plan --test-cases` writes `test-checks-plan.md`, whose steps let the agent make as many checks for a test case as its pass criteria need.

Jama Connect® is a registered trademark of Jama Software, Inc.
