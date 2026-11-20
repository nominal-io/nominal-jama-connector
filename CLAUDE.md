# nominal-jama-connector

Everything a person reads in this repo follows the Nominal docs hub's writing rules:

@../pub-docs/CLAUDE.md

If that import comes up empty, pub-docs isn't checked out beside this repo. Read
https://github.com/nominal-io/pub-docs/blob/main/CLAUDE.md instead. Its "Building and checking"
and "Repo conventions" sections are about pub-docs itself and don't apply here.

The rules cover the docs in `docs/`, the README, docstrings, error messages and code comments.
Docstrings are Google style, and the API reference is built from them, so a docstring change is a
docs change. `docs/CLAUDE.md` has the rules for the pages themselves.

## Layout

One package, `nominal-checks-from-jama` (import `nominal_checks_from_jama`, CLI
`nominal-checks-from-jama`). It makes Nominal checks from a Jama Connect project's requirements,
and never writes to Jama.

The work is in steps, each a function from the previous step's data to its own, with an on-disk
file between steps. Keep them separate: a step reads only the previous step's data.

1. `requirements.py`: read Jama (through `_jama/`) into `Requirements` (`requirements.json`).
2. `checks.py`: make a `CheckSpec` per requirement (`checks.json`). It calls neither Jama nor
   Nominal. `markers.py` holds the channel finder, the part users most often change.
3. Two outputs, each reading only `Checks`:
   - `agent_plan.py`: `checks-plan.md`, instructions for an agent connected to Nominal.
   - `nominal_sync.py`: the checklist in Nominal, through `_nominal.py`, the only module that calls
     Nominal. Jama is the source of truth for check text; nothing is stored between syncs.

- `pipeline.py`: the steps chained, for the CLI and callers. `files.py`: the files' JSON layout.
- `nominal-checks-from-jama.py`: runs the CLI from the checkout without installing the package.
  `requirements.txt` is exported from `uv.lock` with `just export-requirements`; re-export it when
  the lock changes.
- `docs/`: the user docs, which the Nominal docs hub will publish.
- `tests/`: unit tests. They mock Jama with respx and Nominal with an in-memory fake, and use
  invented fixtures only. `tests/golden/` holds each step's file for the invented project.
- `scripts/`: checks against a real Jama instance, which CI doesn't run.

## Commands

`just install`, `just check` (format, lint, types), `just test`, `just build-docs`,
`just serve-docs`. Run `just check`, `just test` and `just build-docs` before calling a change done.

## Rules

- The repo will be public. Fixtures, examples and comments use invented names and hosts
  (`example.jamacloud.com`), never a customer's.
- Jama's name says only what the tool reads from. Nothing in code, docs or what the tool writes
  into Nominal may suggest a partnership with Jama or an endorsement by it: no "official",
  "certified", "partner" or "supported by Jama", and no Jama logo.
- Jama's ids are strings in every model, whatever type the wire sends.
- Errors are classified by HTTP status, never by message text, and never include a response body.
- A listing that stops at a cap says so (`truncated`); it never returns a partial set as complete.
- `sync` rewrites only what Jama owns: a check's title, and its description up to the line that
  links to Jama. It keeps each check's condition and notes, removes a check only when asked, and
  sends everything else in the checklist back unchanged.
