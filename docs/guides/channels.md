# Mark channels in requirements

{.lead}
A channel a requirement marks becomes a checklist variable, ready for the check's condition, and your agent's plan lists it for the requirement.
The tool reads only marked names, so a requirement's text decides which channels it uses.

## Mark a channel in Jama Connect

Put the channel's name in backticks, or in code formatting, in the requirement's description:

```text
The `brake_temp` stays below 450 °C during a hot stop.
```

A name is one word with no spaces, and must match the channel's name in Nominal exactly.
Each marked channel becomes a variable named for the requirement and the channel, such as `WA-REQ-101: brake_temp`, reading the data source named `default`. To read another, set `ref_name` under `[nominal]` in `jama-checks.toml`.

## Accept other marks

If your requirements already mark channels with `{brake_temp}`, `[brake_temp]` or `<brake_temp>`, turn those on in `jama-checks.toml`:

```toml
[nominal]
channel_markers = ["{}", "<>"]
```

## Add your own mark

The marks are defined in `PAIRS` in `src/nominal_checks_from_jama/markers.py`, each a pattern whose first group is the name.
To accept `$brake_temp$`, add an entry:

```python
PAIRS: dict[str, re.Pattern[str]] = {
    "{}": re.compile(r"\{([^{}\s]+)\}"),
    "[]": re.compile(r"\[([^\[\]\s]+)\]"),
    "<>": re.compile(r"<([^<>\s]+)>"),
    "$$": re.compile(r"\$([^$\s]+)\$"),
}
```

Then turn it on with `channel_markers = ["$$"]`.

## Find channels your own way

If your requirements follow a structure of their own, write a function that takes a requirement and returns its channel names, and pass it to `build_checks`.
A requirement has its text as plain text and as Jama Connect's HTML. This one reads a line such as `Channel: engine.rpm`:

```python
from nominal_checks_from_jama import Requirement, build_checks, read_requirements


def channels_from_lines(requirement: Requirement) -> list[str]:
    return [
        line.split(":", 1)[1].strip()
        for line in requirement.text.splitlines()
        if line.lower().startswith("channel:")
    ]


checks = build_checks(read_requirements("jama-checks.toml"), channels_from_lines)
checks.save("checks.json")
```

Then write the plan or sync from the file:

```sh
python nominal-checks-from-jama.py agent-plan --from checks.json
```

## Replace the whole step

Both outputs read only `checks.json`. To decide everything a check holds yourself, write `checks.json` with your own code, in the layout [Files](../reference/files.md#checks-file) describes, starting from `requirements.json`:

```sh
python nominal-checks-from-jama.py read
```

Keep each description's last line, the link to Jama Connect: it's how later runs find the check.

Jama Connect® is a registered trademark of Jama Software, Inc.
