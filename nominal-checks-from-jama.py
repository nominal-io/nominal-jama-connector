"""Run the tool from this folder, without installing it: ``python nominal-checks-from-jama.py agent-plan``.

The Python that runs it needs the tool's dependencies, which
``python -m pip install -r requirements.txt`` installs.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))

try:
    from nominal_checks_from_jama.cli import main
except ModuleNotFoundError as error:
    sys.exit(
        f"{error.name} isn't installed for the Python at {sys.executable}. "
        f'Install the dependencies with: python -m pip install -r "{HERE / "requirements.txt"}"'
    )

# the name messages and usage lines give the tool, so their commands run as typed
script = sys.argv[0] if sys.argv and sys.argv[0] else "nominal-checks-from-jama.py"
main(prog_name=f'python "{script}"' if " " in script else f"python {script}")
