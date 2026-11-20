"""Make Nominal checks from the requirements in a Jama Connect project.

The work happens in steps, each a function that takes the previous step's data and returns its own:

1. :func:`read_requirements` reads the requirements from Jama (``requirements.json``).
2. :func:`build_checks` makes a check for each one (``checks.json``).
3. Either output:

   - :func:`write_agent_plan` writes instructions for an agent connected to Nominal (``checks-plan.md``).
   - :func:`sync` creates or updates the checklist in Nominal itself.

:func:`checks_from_jama` runs steps 1 and 2 together.
"""

from nominal_checks_from_jama._nominal import ChecklistConflict, NominalError
from nominal_checks_from_jama.agent_plan import AgentPlan, write_agent_plan
from nominal_checks_from_jama.checks import Checks, CheckSpec, build_checks, lineage
from nominal_checks_from_jama.config import AuthKind, Config, JamaSettings, NominalSettings
from nominal_checks_from_jama.files import FileFormatError
from nominal_checks_from_jama.kinds import ItemKind
from nominal_checks_from_jama.markers import PAIRS, ChannelFinder, channel_names, marked_channels
from nominal_checks_from_jama.nominal_sync import (
    Difference,
    Field,
    Outcome,
    Result,
    SyncError,
    SyncPlan,
    SyncResult,
    VariableResult,
    plan_sync,
    sync,
)
from nominal_checks_from_jama.pipeline import checks_from_file, checks_from_jama
from nominal_checks_from_jama.requirements import ReadError, Requirement, Requirements, Source, read_requirements

__version__ = "0.2.0"

__all__ = [
    "PAIRS",
    "AgentPlan",
    "AuthKind",
    "ChannelFinder",
    "CheckSpec",
    "ChecklistConflict",
    "Checks",
    "Config",
    "Difference",
    "Field",
    "FileFormatError",
    "ItemKind",
    "JamaSettings",
    "NominalError",
    "NominalSettings",
    "Outcome",
    "ReadError",
    "Requirement",
    "Requirements",
    "Result",
    "Source",
    "SyncError",
    "SyncPlan",
    "SyncResult",
    "VariableResult",
    "build_checks",
    "channel_names",
    "checks_from_file",
    "checks_from_jama",
    "lineage",
    "marked_channels",
    "plan_sync",
    "read_requirements",
    "sync",
    "write_agent_plan",
]
