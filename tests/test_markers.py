from __future__ import annotations

import pytest

from nominal_checks_from_jama._jama import html_to_text
from nominal_checks_from_jama.markers import channel_names


def names(description: str, markers: tuple[str, ...] = ()) -> tuple[str, ...]:
    return channel_names(description, html_to_text(description), markers)


@pytest.mark.parametrize(
    ("description", "markers", "expected"),
    [
        ("<p>The `bus_voltage` stays under 28 V.</p>", (), ("bus_voltage",)),
        ("<p>The <code>bus.voltage</code> and `current` agree.</p>", (), ("bus.voltage", "current")),
        ("<p>`a` then `b` then `a` again.</p>", (), ("a", "b")),
        ("<p>`two words` is not a name.</p>", (), ()),
        ("<p>{voltage} and [current] and &lt;temp&gt;</p>", (), ()),
        ("<p>{voltage} and [current] and &lt;temp&gt;</p>", ("{}", "[]", "<>"), ("voltage", "current", "temp")),
        ("<p>[current] but not {voltage}</p>", ("[]",), ("current",)),
        ("<p>When a &lt; b and c &gt; d</p>", ("<>",), ()),
        ("<p>Keep <code>x y</code> out</p>", (), ()),
    ],
)
def test_channel_names(description: str, markers: tuple[str, ...], expected: tuple[str, ...]) -> None:
    assert names(description, markers) == expected
