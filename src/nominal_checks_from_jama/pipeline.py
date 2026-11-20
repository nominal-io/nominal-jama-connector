"""The steps chained together: from Jama, or from either step's file, to the checks.

Each step also runs on its own; see :mod:`~nominal_checks_from_jama.requirements`,
:mod:`~nominal_checks_from_jama.checks`, :mod:`~nominal_checks_from_jama.agent_plan` and
:mod:`~nominal_checks_from_jama.nominal_sync`.
"""

from __future__ import annotations

from pathlib import Path

from nominal_checks_from_jama import files
from nominal_checks_from_jama._jama import JamaClient
from nominal_checks_from_jama.checks import KIND as CHECKS
from nominal_checks_from_jama.checks import Checks, build_checks
from nominal_checks_from_jama.config import Config
from nominal_checks_from_jama.kinds import ItemKind
from nominal_checks_from_jama.markers import ChannelFinder
from nominal_checks_from_jama.requirements import KIND as REQUIREMENTS
from nominal_checks_from_jama.requirements import Requirements, read_requirements


def checks_from_jama(
    config: Config,
    *,
    find_channels: ChannelFinder | None = None,
    jama: JamaClient | None = None,
    kind: ItemKind = ItemKind.REQUIREMENTS,
) -> Checks:
    """Read the project's requirements or test cases from Jama and make their checks.

    Args:
        config (Config): The settings: the Jama project, and the channel markers that are on.
        find_channels (ChannelFinder | None): Finds the channel names in an item; the tool's own,
            with the settings' markers, when None.
        jama (JamaClient | None): The Jama client; one signed in from the settings when None.
        kind (ItemKind): Requirements or test cases.

    Returns:
        Checks: The checks.
    """
    requirements = read_requirements(config, jama=jama, kind=kind)
    return build_checks(requirements, find_channels, markers=config.nominal.channel_markers)


def checks_from_file(
    path: str | Path,
    *,
    markers: tuple[str, ...] = (),
    find_channels: ChannelFinder | None = None,
) -> Checks:
    """The checks from a checks file, or made from a requirements or test cases file.

    Args:
        path (str | Path): The file.
        markers (tuple[str, ...]): The channel markers that are on, for a requirements file.
        find_channels (ChannelFinder | None): Finds the channel names, for a requirements file; the
            tool's own when None.

    Returns:
        Checks: The checks.

    Raises:
        FileFormatError: When the file is neither.
    """
    kind = files.kind_of(path)
    if kind == CHECKS:
        return Checks.load(path)
    if kind == REQUIREMENTS:
        return build_checks(Requirements.load(path), find_channels, markers=markers)
    raise files.FileFormatError(f"{path} isn't a requirements or checks file from this tool.")
