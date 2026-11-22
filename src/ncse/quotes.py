"""Matching quotations against the article text (D-022).

A quotation must be a verbatim passage of the article's text file. The only
tolerated difference is whitespace: any run of spaces, tabs and line breaks
counts as a single space, and whitespace at the start and end is ignored.
Everything else (spelling, punctuation, quotation marks, capitals) must match
exactly.
"""

import re

_WS = re.compile(r"\s+")


def normalize(text: str) -> tuple[str, list[int]]:
    """Collapse whitespace; return the new string and, for each of its
    characters, the position of that character in the original text."""
    out: list[str] = []
    where: list[int] = []
    pending_space = False
    for i, ch in enumerate(text):
        if ch.isspace():
            pending_space = bool(out)  # no space before the first character
            continue
        if pending_space:
            out.append(" ")
            where.append(i - 1)
            pending_space = False
        out.append(ch)
        where.append(i)
    return "".join(out), where


def squeeze(text: str) -> str:
    """Whitespace-normalized form of a text, without the position map."""
    return _WS.sub(" ", text).strip()


def find_all(text: str, quote: str) -> list[tuple[int, int]]:
    """All places where `quote` occurs in `text` (whitespace-tolerant), as
    (start, end) character positions in the original `text`."""
    norm_text, where = normalize(text)
    norm_quote = squeeze(quote)
    if not norm_quote:
        return []
    hits = []
    pos = norm_text.find(norm_quote)
    while pos != -1:
        start = where[pos]
        end = where[pos + len(norm_quote) - 1] + 1
        hits.append((start, end))
        pos = norm_text.find(norm_quote, pos + 1)
    return hits


def contains(container: str, part: str, ignore_case: bool = False) -> bool:
    """Whether `part` occurs in `container`, whitespace-tolerant."""
    a, b = squeeze(container), squeeze(part)
    if ignore_case:
        a, b = a.casefold(), b.casefold()
    return bool(b) and b in a
