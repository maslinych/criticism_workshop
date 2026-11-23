"""Long articles in parts (D-034).

An article longer than `annotation.max_part_chars` is sent to the analyst in
parts, one request per part, because one answer for the whole article would
take longer than the LLM service allows or exceed the length limit of an
answer. The reviewer reviews the same parts. The split happens only while the
article is processed: the corpus text is never changed, and the results of the
parts are joined back into one result for the article, numbered and positioned
as if the article had been annotated in one go.

- **Splitting.** The article is cut into the smallest number of parts that are
  no longer than the limit, of roughly equal length, at paragraph breaks (a
  blank line), preferably one after the end of a sentence. Only where a paragraph is longer than the limit is it cut at a
  line break, then at the end of a sentence, then at a space. The split depends
  only on the text and the limit, so a run that is resumed gets the same parts.
- **Context.** With each part the model receives, as context it must not
  annotate, the article's beginning and the text just before the part, so that
  it knows which book or author a review is about.
- **Joining.** The passages of the parts are numbered on (p01, p02, … over the
  whole article), their positions are counted from the start of the article,
  and each passage records the part it came from.

All functions here are pure, so that they can be tested directly.
"""

import math
import re

GAP = "\n\n[…]\n\n"  # marks text left out of the context
_ID = re.compile(r"\bp(\d+)(-s\d+)?\b")


# ---------------------------------------------------------------- splitting


def _breaks(text: str, lo: int, hi: int) -> list[list[int]]:
    """Possible cut positions in text[lo:hi], best kind first: after a blank
    line that follows the end of a sentence, after any blank line, after a line
    break, after the end of a sentence, after a space. A cut position is where
    the next part starts."""
    window = text[lo:hi]
    kinds = [r"[.!?:][\"'”’)]*[ \t]*\n[ \t]*\n\s*",  # blank line after the end of a sentence
             r"\n[ \t]*\n\s*",  # any blank line (in this corpus also where a text box ends mid-sentence)
             r"\n\s*", r"[.!?][\"'”’)]*\s+", r"\s+"]
    return [[lo + m.end() for m in re.finditer(k, window) if 0 < lo + m.end() < len(text)] for k in kinds]


def split(text: str, max_chars: int) -> list[tuple[int, int]]:
    """The parts of an article as (start, end) positions in its text. An article
    no longer than `max_chars` is a single part."""
    if len(text) <= max_chars:
        return [(0, len(text))]
    parts, start = [], 0
    while len(text) - start > max_chars:
        left = math.ceil((len(text) - start) / max_chars)  # parts still needed
        target = start + (len(text) - start) / left
        # The cut must leave this part within the limit and the rest splittable
        # into left-1 parts within the limit.
        lo = max(start + 1, len(text) - (left - 1) * max_chars)
        hi = start + max_chars
        cut = None
        for kind in _breaks(text, lo, hi + 1):
            if kind:
                cut = min(kind, key=lambda c: (abs(c - target), c))
                break
        if cut is None:  # no space at all: cut mid-word
            cut = round(min(max(target, lo), hi))
        parts.append((start, cut))
        start = cut
    parts.append((start, len(text)))
    return parts


def context(text: str, start: int, opening: int, before: int) -> str:
    """The context sent with the part that begins at `start`: the first
    `opening` characters of the article and the `before` characters just before
    the part, each cut at a space, joined with a mark for the text left out.
    Empty for the first part."""
    if start == 0:
        return ""
    if start <= opening + before:
        return text[:start].rstrip()
    head = text[:opening]
    head = head[:head.rfind(" ")] if " " in head else head
    tail_start = start - before
    space = text.find(" ", tail_start, start)
    tail = text[space + 1 if space != -1 else tail_start:start]
    return head.rstrip() + GAP + tail.strip()


def part_name(article_id: str, number: int, count: int) -> str:
    """File name (without .json) of the record of one part."""
    return f"{article_id}.part{number}of{count}"


# ---------------------------------------------------------------- joining


def renumber(item_id: str, offset: int) -> str:
    """Shift the passage number of the first identifier in a text (p03, p03-s02,
    or a message that begins with one) by `offset`."""
    if not offset:
        return item_id
    return _ID.sub(lambda m: f"p{int(m.group(1)) + offset:02d}{m.group(2) or ''}", item_id, count=1)


def answer_passages(result: dict) -> int:
    """How many passages the answer for a part had, including failed ones (which
    keep their numbers, checks.check_analyst)."""
    return len(result["passages"]) + sum(1 for f in result["failed"] if f["item"] == "passage")


def join_analyst(parts: list[dict]) -> tuple[dict, list[dict]]:
    """Join the checked results of the parts of one article.

    `parts` lists, in order, {"part", "start", "end", "result", "flags"} for each
    part. Returns the result for the whole article (same shape as for an
    article annotated in one go, plus `part` on every passage and the list of
    `parts`) and its flags."""
    passages, failed, flags = [], [], []
    offset = 0
    for p in parts:
        res, k, shift = p["result"], p["part"], p["start"]
        for pas in res["passages"]:
            pid = renumber(pas["passage_id"], offset)
            passages.append({**pas, "passage_id": pid, "part": k,
                             "quote_start": pas["quote_start"] + shift, "quote_end": pas["quote_end"] + shift,
                             "statements": [{**s, "statement_id": renumber(s["statement_id"], offset)}
                                            for s in pas["statements"]]})
        for item in res["failed"]:
            failed.append({**item, "where": renumber(item["where"], offset), "part": k,
                           "errors": [renumber(e, offset) if e.startswith(("passage p", "statement p")) else e
                                      for e in item["errors"]]})
        for f in p["flags"]:
            g = {**f, "where": renumber(f["where"], offset), "part": k}
            if f["flag"] in ("repeated_quote", "repeated_statement"):
                g["detail"] = re.sub(r"(as|to) (p\d+(?:-s\d+)?)$",
                                     lambda m: f"{m.group(1)} {renumber(m.group(2), offset)}", f["detail"])
            flags.append(g)
        offset += answer_passages(res)
    tolerance = parts[0]["result"]["quote_tolerance"]
    return ({"passages": passages, "failed": failed, "quote_tolerance": tolerance,
             "parts": [{"part": p["part"], "start": p["start"], "end": p["end"]} for p in parts]}, flags)


def part_of_analyst(result: dict, number: int) -> dict:
    """The analyst's joined result restricted to the passages of one part, as the
    reviewer of that part sees them."""
    return {**result, "passages": [p for p in result["passages"] if p.get("part") == number]}
