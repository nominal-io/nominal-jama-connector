"""Build or serve the docs with nominal-sphinx-theme's newest commit.

``just build-docs`` and ``just serve-docs`` run this. It builds with the commit at the tip of the
theme's main branch, so the docs pick up theme changes without waiting for uv.lock to move. If
that build fails and a build with the commit in uv.lock succeeds, it uses the one in uv.lock. It
also uses the one in uv.lock when GitHub can't be reached.

Exit codes for ``build``: 0 when a build succeeded, otherwise the failed build's exit code.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

THEME = "https://github.com/nominal-io/nominal-sphinx-theme"
ROOT = Path(__file__).resolve().parent.parent
BUILD = ["sphinx-build", "-E", "-W", "--keep-going", "-b", "dirhtml", "docs", "docs/_build/dirhtml"]


def say(message: str) -> None:
    """Print a status line, apart from Sphinx's own output."""
    print(f"docs: {message}", file=sys.stderr, flush=True)


def newest_theme() -> str | None:
    """The commit at the tip of the theme's main branch, or None if GitHub can't be reached."""
    try:
        listing = subprocess.run(
            ["git", "ls-remote", THEME, "refs/heads/main"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return listing.split()[0] if listing.strip() else None


def uv_run(theme: str | None, command: list[str]) -> int:
    """Run a command in the docs environment, with the theme at commit ``theme`` or as uv.lock pins it."""
    with_theme = ["--with", f"nominal-sphinx-theme @ git+{THEME}@{theme}"] if theme else []
    return subprocess.run(["uv", "run", "--group", "docs", *with_theme, *command], cwd=ROOT, check=False).returncode


def build() -> tuple[int, str | None]:
    """Build the docs, and return the exit code and the theme commit used (None for uv.lock's)."""
    theme = newest_theme()
    if theme is None:
        say("can't reach GitHub, so building with the theme commit in uv.lock")
    else:
        say(f"building with the theme's newest commit, {theme[:7]}")
        if uv_run(theme, BUILD) == 0:
            return 0, theme
        say("the build failed with the theme's newest commit, so building again with the commit in uv.lock")
    code = uv_run(None, BUILD)
    if code == 0:
        if theme is not None:
            say(f"the build succeeded with the commit in uv.lock, so the theme's newest commit, {theme[:7]}, broke it")
        return 0, None
    # it failed with both commits, so the problem is in this repo, not the theme
    return code, theme


def main() -> int:
    """Run ``build`` or ``serve``."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="build into docs/_build/dirhtml; warnings fail the build")
    serve = commands.add_parser("serve", help="build, then serve on http://127.0.0.1:PORT, rebuilding on edits")
    serve.add_argument("--port", default="8000")
    args = parser.parse_args()

    code, theme = build()
    if args.command == "build":
        return code
    # serve even if the build failed, so its errors show while you fix them
    autobuild = [
        "sphinx-autobuild",
        "-b",
        "dirhtml",
        "--port",
        args.port,
        "docs",
        "docs/_build/dirhtml",
        "--watch",
        "src",
    ]
    return uv_run(theme, ["--with", "sphinx-autobuild", *autobuild])


if __name__ == "__main__":
    sys.exit(main())
