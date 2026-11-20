"""Finding the channel names a requirement marks: the part of step 2 you're most likely to change.

Backticks (`` `voltage` ``) and Jama's code formatting always mark a channel. The pairs in
:data:`PAIRS`, ``{}``, ``[]`` and ``<>``, do when ``[nominal] channel_markers`` turns them on. A
marked name is one token with no whitespace, so a comparison such as ``a < b and c > d`` doesn't
match ``<>``.

To mark channels another way, add a pair to :data:`PAIRS`, or write your own
:data:`ChannelFinder` and pass it to :func:`~nominal_checks_from_jama.checks.build_checks`.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Iterable, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nominal_checks_from_jama.requirements import Requirement

ChannelFinder = Callable[["Requirement"], Sequence[str]]
"""Finds the channel names in one requirement, in the order they should become variables."""

_BACKTICKS = re.compile(r"`([^`\s]+)`")
_CODE = re.compile(r"<code\b[^>]*>(.*?)</code>", re.IGNORECASE | re.DOTALL)
_TAG = re.compile(r"<[^>]*>")

PAIRS: dict[str, re.Pattern[str]] = {
    "{}": re.compile(r"\{([^{}\s]+)\}"),
    "[]": re.compile(r"\[([^\[\]\s]+)\]"),
    "<>": re.compile(r"<([^<>\s]+)>"),
}
"""Pairs that can mark a channel name, besides backticks, by the name ``channel_markers`` uses.

Each pattern's first group is the name. Add an entry to make a new pair available to
``channel_markers``.
"""


def channel_names(description_html: str, text: str, markers: Iterable[str] = ()) -> tuple[str, ...]:
    """The channel names a requirement marks, in the order they first appear.

    Args:
        description_html (str): The requirement's description as Jama stores it, for code formatting.
        text (str): The same description as plain text, for the other markers.
        markers (Iterable[str]): The pairs from :data:`PAIRS` that are on.

    Returns:
        tuple[str, ...]: The names, each once.
    """
    found: list[tuple[int, str]] = []
    for match in _CODE.finditer(description_html):
        name = html.unescape(_TAG.sub("", match.group(1))).strip()
        if name and not any(c.isspace() for c in name):
            # Code formatting has no position in the plain text; place it by its first occurrence there.
            at = text.find(name)
            found.append((at if at >= 0 else len(text), name))
    for pattern in (_BACKTICKS, *(PAIRS[m] for m in markers)):
        found.extend((match.start(), match.group(1)) for match in pattern.finditer(text))
    return tuple(dict.fromkeys(name for _, name in sorted(found, key=lambda pair: pair[0])))


def marked_channels(markers: Iterable[str] = ()) -> ChannelFinder:
    """The tool's own :data:`ChannelFinder`: the names marked with backticks, code formatting and ``markers``.

    Args:
        markers (Iterable[str]): The pairs from :data:`PAIRS` that are on.

    Returns:
        ChannelFinder: The finder.
    """
    on = tuple(markers)

    def find(requirement: Requirement) -> Sequence[str]:
        return channel_names(requirement.html, requirement.text, on)

    return find
