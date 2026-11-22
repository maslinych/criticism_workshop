"""Find NCSE boxes whose text was invented by the OCR model (decision D-017).

NCSE v2.0 was read by an image-to-text language model. Sometimes that model did
not copy the page but kept writing: it repeated a sentence in a loop until it
was cut off, or it produced a plausible-looking page of its own. Such text is
not from the periodical, so the boxes holding it are left out of the corpus and
listed, with the reason, in `excluded_boxes.csv`.

A box counts as invented when either of these tests is true:

1. **Output limit reached.** NCSE records how many tokens (word pieces) the OCR
   model wrote for each box (`completion_tokens`). Tall boxes were read in
   several parts (`segment_count`). The model stopped after 2,000 tokens per
   part: thousands of boxes have exactly 2,000, far more than any other value.
   A box where every part reached the limit was cut off in the middle of a
   loop or an invented page.
2. **Repeated loop.** At least 30% of the box's 8-word sequences occur more than
   once in the same box. Real text rarely repeats itself like this; lists and
   tables of contents stay well below the threshold (see `docs/decisions.md`).

Remarks addressed to the user ("Certainly! Below is the extracted table…") and
picture descriptions ("The image depicts…") occur only in table and figure
boxes, which are left out anyway (D-013).

The functions are pure (they take plain values), so they can be tested without
the real data. The thresholds come from `config.yaml` (`invented:`).
"""

import re
from collections import Counter

# Words that contain at least one letter. Dot leaders ". . . ." and runs of
# numbers in lists are not counted as repetition.
_WORD = re.compile(r"[A-Za-z]")


def repeated_share(text: str, n: int) -> float:
    """Share of the n-word sequences in `text` that repeat an earlier one.

    0.0 means no sequence occurs twice; 0.9 means nearly the whole text is a
    loop. Texts shorter than 3*n words get 0.0 (too short to judge).
    """
    words = [w for w in text.split() if _WORD.search(w)]
    if len(words) < 3 * n:
        return 0.0
    seqs = Counter(" ".join(words[i : i + n]) for i in range(len(words) - n + 1))
    return sum(c - 1 for c in seqs.values() if c > 1) / (len(words) - n + 1)


def invented_reason(content: str, completion_tokens: int, segment_count: int, settings: dict) -> str | None:
    """Return why a box counts as invented text, or None if it does not."""
    limit = settings["token_limit"]
    if completion_tokens >= limit * max(1, segment_count):
        return f"output limit: the OCR model wrote {completion_tokens} tokens, the limit of {limit} per part"
    share = repeated_share(content, settings["repeat_ngram"])
    if share >= settings["repeat_share"]:
        return f"loop: {share:.0%} of {settings['repeat_ngram']}-word sequences are repeats"
    return None
