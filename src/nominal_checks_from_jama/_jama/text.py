"""Turning Jama's rich text into plain text."""

from __future__ import annotations

import re
from html.parser import HTMLParser

# Tags that end a line. Table cells are included: cells run together would read "1020" for two
# values, 10 and 20.
_BLOCK_TAGS = frozenset(
    {
        "address",
        "article",
        "blockquote",
        "br",
        "dd",
        "div",
        "dl",
        "dt",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "li",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "tbody",
        "td",
        "th",
        "thead",
        "tr",
        "ul",
    }
)
_IGNORED_TAGS = frozenset({"script", "style"})


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignoring = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _IGNORED_TAGS:
            self._ignoring += 1
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _IGNORED_TAGS:
            self._ignoring = max(0, self._ignoring - 1)
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignoring:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    r"""The text of a Jama rich-text (TEXT) field, without markup.

    Paragraphs, list items, table cells and line breaks become line breaks, so a requirement
    written as a list stays readable. Character references such as ``&deg;`` are decoded, and the
    contents of ``<script>`` and ``<style>`` are dropped.

    Args:
        html (str): The field's HTML.

    Returns:
        str: The text, with one line break between blocks and no leading or trailing whitespace.

    Example:
        >>> html_to_text("<p>Hold 85&deg;C for:</p><ul><li>10 min</li><li>20 min</li></ul>")
        'Hold 85°C for:\n10 min\n20 min'
    """
    collector = _TextCollector()
    collector.feed(html)
    collector.close()
    text = "".join(collector.parts).replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    return re.sub(r"\n{2,}", "\n", text).strip()
