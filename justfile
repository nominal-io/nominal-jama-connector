# Recipes run in PowerShell on Windows (no bash or cygpath needed) and sh elsewhere.
[windows]
set shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

# list the recipes
default:
    @just --list

# development install, with the dev tools
install:
    uv sync

# run the CLI from this checkout, in the current folder: `just run init`, `just run sync --dry-run`
[no-cd]
run *args:
    uv run --project "{{ justfile_directory() }}" nominal-checks-from-jama {{ args }}

# run the unit tests
test *args:
    uv run pytest {{ args }}

# check the Jama reader against a real Jama project; see scripts/jama_live_check.py for its settings
test-live *args:
    uv run python scripts/jama_live_check.py {{ args }}

# check static typing
check-types:
    uv run mypy

# check code formatting | fix with `just fix-format`
check-format:
    uv run ruff format --check

# check lint and import ordering | fix with `just fix-imports`
check-imports:
    uv run ruff check

# run all static analysis checks
check: check-format check-types check-imports

# format the code
fix-format:
    uv run ruff format

# fix lint and import ordering where ruff can
fix-imports:
    uv run ruff check --fix

# format and fix everything ruff can
fix: fix-format fix-imports

# write requirements.txt from uv.lock: the runtime dependencies, for `python -m pip install -r requirements.txt`
export-requirements:
    uv export --format requirements-txt --no-default-groups --no-emit-project --output-file requirements.txt

# build the wheel and sdist into dist/
package:
    uv build

# build the docs into docs/_build/dirhtml; warnings fail the build, as in CI.
# Uses nominal-sphinx-theme's newest commit, or the one in uv.lock if that build fails (scripts/docs.py)
build-docs:
    uv run --no-project scripts/docs.py build

# serve the docs on http://127.0.0.1:8000, rebuilding on page or code edits (`--port 8001` for another port)
[arg("port", long="port")]
serve-docs port="8000":
    uv run --no-project scripts/docs.py serve --port {{ port }}
