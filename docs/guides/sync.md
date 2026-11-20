# Sync checks with the tool

{.lead}
`sync` keeps a published Nominal checklist with a check for each requirement in the Jama Connect project.
It writes no conditions: you add each one in Nominal.

## Create the checklist

```sh
python nominal-checks-from-jama.py sync
```

```text
  created: WA-REQ-101 Brake temperature
  created: WA-REQ-102 Pedal force
Created the checklist: 2 created.
https://app.gov.nominal.io/w/<workspace>/checklists/<checklist RID>
```

The first sync creates and publishes the checklist, named `<Jama project name> requirements`, and assigns it to you.
Each check has:

- the title `<document key> <name>`, such as `WA-REQ-101 Brake temperature`
- the requirement's text as its description, then a line linking to the requirement in Jama Connect
- no condition, so it's left out of results until you add one
- priority P3

The checklist's properties `jama_host`, `jama_project` and `jama_items` mark it as this project's requirements checklist. Later syncs find it by them, so renaming it in Nominal is fine.
Each channel a requirement [marks](channels.md) becomes a checklist variable, such as `WA-REQ-101: brake_temp`.

To see what a sync would do without writing anything, add `--dry-run`.

## Add a condition to a check

1. Open the checklist's link.
2. Click **EDIT CHECKLIST**.
3. Select a check, and give it a condition under **WHEN**.
4. Click **PUBLISH**, choose **Publish as latest version…**, enter a **Message**, and click **PUBLISH**.

To have your agent draft the conditions instead, see [Switch from the sync to your agent](switch.md).

## Run the checklist on a run

Open the run's **Checklist executions** tab and click **EXECUTE CHECKLIST**.
Checks without a condition are left out of the result.
[Workbooks: Checklists](site:/platform/workbooks/#checklists) explains checklists and checks.

## Sync again after Jama changes

Run `sync` again whenever requirements change in Jama Connect.
Jama Connect is the source of truth for each check's title and description:

- A new requirement gets a check.
- A check whose title or description differs from its requirement is rewritten from Jama Connect, keeping its condition. The sync prints each difference:

  ```text
    updated from Jama: WA-REQ-102 Pedal force
        title:
          --- Nominal
          +++ Jama
          @@ -1 +1 @@
          -WA-REQ-102 Pedal forse
          +WA-REQ-102 Pedal force
  ```

- A check whose requirement is gone from Jama Connect is kept and listed. Add `--remove-missing` to remove it.
- A check someone deleted in Nominal is made again.
- Checks and variables that don't come from Jama Connect are left alone.

Differences only in spacing or line breaks don't count.

To choose what a sync rewrites, use `--update`:

| Option | What a sync rewrites in a check that differs |
| --- | --- |
| `--update all` (the default) | Its title and description |
| `--update title` | Its title |
| `--update description` | Its description |
| `--update none` | Nothing: it lists the differences, and still adds checks for new requirements |

If someone changes the checklist while a sync runs, the sync stops without writing. Run it again.

## Settings

Set these under `[nominal]` in `jama-checks.toml` before the first sync: `checklist_name` for another name, `priority` for new checks' priority, `profile` for another Nominal profile, and `ref_name` for the data source that variables read.
[Files](../reference/files.md) lists every setting.

Jama Connect® is a registered trademark of Jama Software, Inc.
