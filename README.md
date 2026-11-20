# nominal-jama-connector

`nominal-checks-from-jama` makes Nominal checks from the requirements in a Jama Connect® project.
It writes instructions your agent follows to build the checklist and draft its conditions, or keeps
the checklist itself. It reads from Jama Connect and never writes to it.

The docs are in [docs/](docs/).

## Run it

```sh
git clone https://github.com/nominal-io/nominal-jama-connector
cd nominal-jama-connector
python -m pip install -r requirements.txt
python nominal-checks-from-jama.py init
python nominal-checks-from-jama.py agent-plan --target <run or asset RID>
```

The [quickstart](docs/index.md) explains each step.
To use it from your own code, install the package: `python -m pip install .`

## Develop

Needs [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/) 1.46 or later.

```sh
just install               # the package, with the dev tools
just check                 # format, lint and types
just test                  # unit tests
just build-docs            # the docs, into docs/_build/dirhtml
just serve-docs            # the docs on http://127.0.0.1:8000, or another port with --port 8001
just run <command>         # the tool, from this checkout, in the current folder
just export-requirements   # requirements.txt from uv.lock, after the lock changes
```

Jama Connect® is a registered trademark of Jama Software, Inc.
