"""Matching quotations against the article text (D-022, D-028).

A quotation should be a verbatim passage of the article's text file. The
matcher tries three levels, from strict to loose, and reports which one
succeeded:

1. **exact**: the same characters; only whitespace may differ (any run of
   spaces, tabs and line breaks counts as a single space; whitespace at the
   start and end is ignored).
2. **normalised**: the same letters and digits in the same order, ignoring
   everything else and ignoring capitals. This tolerates differences in
   punctuation, the form of quotation marks and dashes, line breaks, words
   broken by a hyphen at a line end ("appre-⏎elated" = "appre-elated"), and
   capitalisation, as long as the words stay the same.
3. **approximate**: like *normalised*, but a few letters or digits may differ
   (inserted, deleted or replaced), as when a model silently corrects an OCR
   error or makes a typo. How many are allowed depends on the length of the
   quotation (`Tolerance`). Such matches are accepted, but flagged by the checks.

A normalised or approximate match must begin and end at word boundaries in the
text, so that a few changed letters cannot turn "any" into "no".

Whatever the level, the match points to a span of the original text, so the
exact source text of every quotation is known.
"""

import re
from dataclasses import dataclass

_WS = re.compile(r"\s+")


@dataclass(frozen=True)
class Tolerance:
    """How many characters may differ in an approximate match: at most
    `max_char_errors`, and at most `max_error_share` of the letters and digits
    of the quoted text (so short phrases must match without any error)."""

    max_char_errors: int = 3
    max_error_share: float = 0.05

    def allowed(self, length: int) -> int:
        return max(0, min(self.max_char_errors, int(length * self.max_error_share)))

    @classmethod
    def from_config(cls, cfg: dict | None) -> "Tolerance":
        cfg = cfg or {}
        return cls(**{k: cfg[k] for k in ("max_char_errors", "max_error_share") if k in cfg})

    def as_dict(self) -> dict:
        return {"max_char_errors": self.max_char_errors, "max_error_share": self.max_error_share}


@dataclass(frozen=True)
class Match:
    start: int        # position in the original text
    end: int
    level: str        # "exact", "normalised" or "approximate"
    char_errors: int  # letters or digits that differ (0 unless approximate)
    count: int        # how many places match at this level (approximate: 1)


# ---------------------------------------------------------------- normal forms


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


def skeleton(text: str) -> tuple[str, list[int]]:
    """Only the letters and digits, in lower case, with the position of each in
    the original text."""
    out: list[str] = []
    where: list[int] = []
    for i, ch in enumerate(text):
        if ch.isalnum():
            folded = ch.casefold()
            out.append(folded)
            where.extend([i] * len(folded))  # casefold can lengthen ("ß" → "ss")
    return "".join(out), where


def squeeze(text: str) -> str:
    """Whitespace-normalized form of a text, without the position map."""
    return _WS.sub(" ", text).strip()


# ---------------------------------------------------------------- matching


def find_all(text: str, quote: str) -> list[tuple[int, int]]:
    """All places where `quote` occurs in `text` (whitespace-tolerant), as
    (start, end) character positions in the original `text`."""
    norm_text, where = normalize(text)
    return _occurrences(norm_text, where, squeeze(quote))


def _occurrences(stream: str, where: list[int], needle: str) -> list[tuple[int, int]]:
    hits = []
    if not needle:
        return hits
    pos = stream.find(needle)
    while pos != -1:
        hits.append((where[pos], where[pos + len(needle) - 1] + 1))
        pos = stream.find(needle, pos + 1)
    return hits


def match(text: str, quote: str, tolerance: Tolerance = Tolerance()) -> Match | None:
    """Find `quote` in `text` at the strictest level that succeeds."""
    hits = find_all(text, quote)
    if hits:
        return Match(*hits[0], level="exact", char_errors=0, count=len(hits))
    sk_text, where = skeleton(text)
    sk_quote, _ = skeleton(quote)
    if not sk_quote:
        return None
    hits = [h for h in _occurrences(sk_text, where, sk_quote) if _whole_words(text, *h)]
    if hits:
        start, end = _widen(text, quote, *hits[0])
        return Match(start, end, level="normalised", char_errors=0, count=len(hits))
    k = tolerance.allowed(len(sk_quote))
    if k == 0:
        return None
    found = _approximate(sk_text, sk_quote, k)
    if found is None:
        return None
    a, b, errors = found
    start, end = where[a], where[b - 1] + 1
    if not _whole_words(text, start, end):
        return None
    start, end = _widen(text, quote, start, end)
    return Match(start, end, level="approximate", char_errors=errors, count=1)


def _whole_words(text: str, start: int, end: int) -> bool:
    """Whether a loose match begins and ends at word boundaries in the text.
    Without this, "no ground" could match the end of "any ground" with one
    changed letter. (Inside a match, word divisions are not checked: "a part"
    matches "apart", as "appre-elated" must match "appre-⏎elated".)"""
    return ((start == 0 or not text[start - 1].isalnum())
            and (end == len(text) or not text[end].isalnum()))


def _widen(text: str, quote: str, start: int, end: int) -> tuple[int, int]:
    """A skeleton match starts and ends with a letter or digit. If the quote
    itself starts or ends with punctuation (a quotation mark, a full stop),
    take in the punctuation next to the match in the text as well, up to the
    nearest space, so that the source span reads like the quote."""
    q = quote.strip()
    if q and not q[0].isalnum():
        while start > 0 and not text[start - 1].isalnum() and not text[start - 1].isspace():
            start -= 1
    if q and not q[-1].isalnum():
        while end < len(text) and not text[end].isalnum() and not text[end].isspace():
            end += 1
    return start, end


def _approximate(text: str, quote: str, k: int, max_candidates: int = 500) -> tuple[int, int, int] | None:
    """Best place in `text` where `quote` occurs with at most `k` edits
    (insertions, deletions, substitutions), as (start, end, edits).

    If the quote matches with at most k edits, then when it is cut into k+1
    pieces at least one piece occurs unchanged. So only the places where some
    piece occurs exactly are examined, each with a small edit-distance table.
    """
    m = len(quote)
    size = m // (k + 1)
    if size == 0:
        return None
    starts = set()
    for p in range(k + 1):
        offset = p * size
        piece = quote[offset: offset + size if p < k else m]
        pos = text.find(piece)
        while pos != -1:
            starts.add(pos - offset)
            if len(starts) > max_candidates:
                return None  # pieces too common to say where the quote is
            pos = text.find(piece, pos + 1)
    best = None
    done_windows: set[int] = set()
    for s in sorted(starts):
        lo = max(0, s - k)
        if lo in done_windows:
            continue
        done_windows.add(lo)
        found = _edit_in_window(quote, text, lo, min(len(text), s + m + k), k)
        if found and (best is None or found[2] < best[2]):
            best = found
            if best[2] == 0:
                break
    return best


def _edit_in_window(quote: str, text: str, lo: int, hi: int, k: int) -> tuple[int, int, int] | None:
    """Smallest edit distance between `quote` and any part of text[lo:hi]
    (free start and end in the text), with that part's (start, end)."""
    window = text[lo:hi]
    n = len(window)
    prev = [0] * (n + 1)
    prev_start = list(range(n + 1))
    for i in range(1, len(quote) + 1):
        cur = [i] + [0] * n
        cur_start = [0] + [0] * n
        qc = quote[i - 1]
        for j in range(1, n + 1):
            best, start = prev[j - 1] + (qc != window[j - 1]), prev_start[j - 1]
            if prev[j] + 1 < best:
                best, start = prev[j] + 1, prev_start[j]
            if cur[j - 1] + 1 < best:
                best, start = cur[j - 1] + 1, cur_start[j - 1]
            cur[j], cur_start[j] = best, start
        prev, prev_start = cur, cur_start
    end = min(range(1, n + 1), key=lambda j: (prev[j], j), default=None)
    if end is None or prev[end] > k:
        return None
    return lo + prev_start[end], lo + end, prev[end]


def contains(container: str, part: str, ignore_case: bool = False) -> bool:
    """Whether `part` occurs in `container`, whitespace-tolerant."""
    a, b = squeeze(container), squeeze(part)
    if ignore_case:
        a, b = a.casefold(), b.casefold()
    return bool(b) and b in a


def contains_loose(container: str, part: str) -> bool:
    """Whether the letters and digits of `part` occur, in order, in
    `container`, ignoring everything else and capitals (normalised level)."""
    b = skeleton(part)[0]
    return bool(b) and b in skeleton(container)[0]
