"""Rebuild articles from NCSE boxes (decision D-016, replacing D-012; provisional).

NCSE boxes are smaller than articles, and their labels are assigned box by box,
so a single review is often labelled "arts" in one box and something else in
the next. The rule used here:

1. Take one issue's boxes in reading order (page, then reading order on the page).
   Some boxes can never go into an article text: figure and table boxes (D-013)
   and boxes of text invented by the OCR model (D-017). They are noted when they
   fall inside an article.
2. Split the issue into *units* at headings. A heading is
   - a title box, or
   - a text box that begins with a heading: a phrase in capitals ending in a full
     stop ("HEINE'S POEMS."), a numbered review ("Art. VI.—") or a book heading
     (title, "By" + author, and place, format or pages within the first 250
     characters: "Christian Theology. By John Calvin. … 8vo. pp. 460.").
   Running page headers ("THE LEADER. [No. 438 …") are not headings. A run of
   title boxes and the heading box after them stay together.
3. A unit that contains at least one box meeting the selection rule (D-002) is
   taken **whole** if it spans at most `max_pages` pages and either
   - its first text box carries the arts topic label (whatever its text type,
     except "advert"), or
   - at least `whole_share` of its text is in boxes meeting the selection rule.
4. Otherwise only the selected part of the unit is taken, as under D-012:
   selected boxes with at most `max_gap` other boxes between them form one
   article, the boxes between are included, and the unit's title is attached
   when the article starts within `max_gap` boxes of it.

The functions here work on plain Python dictionaries, so they can be tested
without the real data. Text is never changed: the article text is the box texts
joined with a blank line.
"""

import re
from dataclasses import dataclass, field

SEPARATOR = "\n\n"

# A phrase of at least five capital letters (spaces, apostrophes, commas, hyphens
# allowed) ending in a full stop, at the very start of the box: "HEINE'S POEMS."
CAPITALS_HEADING = re.compile(r"^\W{0,3}[A-Z][A-Z'’&,\- ]{3,}[A-Z]\.")
# A numbered review in the Monthly Repository: "Art. VI.—", "ART. III."
REVIEW_NUMBER = re.compile(r"^\W{0,3}(?:Art|ART)\. ?[IVXLC]+\b")
# Running page headers, which repeat on every page and do not start an article.
RUNNING_HEADER = re.compile(r"^\W{0,3}(?:THE LEADER|CHRONICLE|THE MONTHLY REPOSITORY|NO\. ?\d|\[NO\.)", re.IGNORECASE)
# Book heading: "By"/"Edited by"/"Translated by" + a capital, and a mark of
# publication (format, pages, volumes, place), both within the first 250 characters.
BOOK_BY = re.compile(r"\b(?:[Bb]y|Par) (?:the )?[A-Z]")
# Four-digit years from 1700 to 1999, for the anachronism flag.
YEAR = re.compile(r"\b1[789]\d\d\b")
BOOK_PUBLICATION = re.compile(r"\b(?:8vo|12mo|4to|18mo|24mo|32mo|[Ff]olio|pp\.|[Vv]ols?\.|London[:,.]|Edinburgh[:,.]|Boston)")


def heading_kind(box: dict) -> str | None:
    """Say what kind of heading a box is, or None if it does not start a unit."""
    if box["class"] == "title":
        return "title box"
    if box["class"] != "text":
        return None
    text = box["content"].lstrip()
    if RUNNING_HEADER.match(text):
        return None
    if CAPITALS_HEADING.match(text):
        return "heading in capitals"
    if REVIEW_NUMBER.match(text):
        return "numbered review"
    start = text[:250]
    if re.match(r"\W{0,3}[A-Z]", text) and BOOK_BY.search(start) and BOOK_PUBLICATION.search(start):
        return "book heading"
    return None


def units(boxes: list[dict]) -> list[list[dict]]:
    """Split an issue's boxes (in reading order) into units that start at headings.

    Boxes before the first heading form a unit of their own. Title boxes and a
    heading box that directly follows them stay in one unit.
    """
    result, current = [], []
    for box in boxes:
        if heading_kind(box) and any(b["class"] != "title" for b in current):
            result.append(current)
            current = []
        current.append(box)
    if current:
        result.append(current)
    return result


def group_positions(positions: list[int], max_gap: int) -> list[tuple[int, int]]:
    """Group sorted positions into (first, last) spans with at most max_gap missing between."""
    groups, first, prev = [], positions[0], positions[0]
    for i in positions[1:]:
        if i - prev - 1 > max_gap:
            groups.append((first, prev))
            first = i
        prev = i
    groups.append((first, prev))
    return groups


@dataclass
class Article:
    boxes: list[dict]          # title boxes first, then text boxes, in reading order
    heading_count: int         # how many of the boxes are heading (title) boxes
    whole: bool                # True if the whole unit was taken (rule step 3)
    notes: list[str] = field(default_factory=list)
    left_out: list[dict] = field(default_factory=list)  # excluded boxes lying inside the article

    @property
    def text(self) -> str:
        return SEPARATOR.join(b["content"] for b in self.boxes)

    @property
    def heading(self) -> str:
        return " | ".join(" ".join(b["content"].split()) for b in self.boxes[: self.heading_count])


def usable(box: dict, exclude_classes: set[str]) -> bool:
    """Can the box go into an article text? Title boxes are handled separately."""
    return box["class"] not in exclude_classes and box["class"] != "title" and not box.get("invented")


def _article(titles: list[dict], items: list[dict], first: int, last: int, whole: bool,
             exclude_classes: set[str], reason: str) -> Article:
    """Build an Article from titles plus items[first..last] (positions in `items`)."""
    span = items[first : last + 1]
    body = [b for b in span if usable(b, exclude_classes)]
    left_out = [b for b in span if not usable(b, exclude_classes)]
    notes = [reason]
    if not titles:
        kind = heading_kind(body[0])
        notes.append(f"starts at a {kind}" if kind else "no heading")
    unselected = [b["bbox_uid"] for b in body if not b["selected"]]
    if unselected:
        notes.append(f"includes {len(unselected)} unselected box(es): {' '.join(unselected)}")
    figures = [b["bbox_uid"] for b in left_out if b["class"] in exclude_classes]
    if figures:
        notes.append(f"omitted figure/table box(es): {' '.join(figures)}")
    invented = [b["bbox_uid"] for b in left_out if b.get("invented")]
    if invented:
        notes.append(f"left out invented text, box(es): {' '.join(invented)}")
    late = []
    for b in titles + body:
        years = [int(y) for y in YEAR.findall(b["content"])]
        if years and max(years) > int(b["issue_date"][:4]) + 1:
            late.append(f"{b['bbox_uid']} ({max(years)})")
    if late:
        # Not excluded: often an OCR misreading of a digit (1881 for 1851), sometimes invented text (D-017).
        notes.append(f"mentions a year later than the issue: {' '.join(late)}")
    if len({b["page_number"] for b in titles + body}) > 1:
        notes.append("crosses page break")
    return Article(boxes=titles + body, heading_count=len(titles), whole=whole, notes=notes, left_out=left_out)


def rebuild_issue(boxes: list[dict], settings: dict, arts_topic: str) -> list[Article]:
    """Build the selected articles of one issue. `boxes` must be in reading order.

    Each box is a dict with: bbox_uid, class, content, issue_date, page_number, n_chars,
    selected, text_type, topics, invented (None, or the reason it was invented).
    `settings` is the `rebuild` section of config.yaml.
    """
    exclude = set(settings["exclude_classes"])
    max_gap = settings["max_gap"]
    articles: list[Article] = []
    for unit in units(boxes):
        titles = [b for b in unit if b["class"] == "title"]
        items = [b for b in unit if b["class"] != "title"]
        pos = [i for i, b in enumerate(items) if usable(b, exclude)]  # positions of usable boxes
        if not pos:
            continue
        chosen = [k for k, i in enumerate(pos) if items[i]["selected"]]  # indexes into pos
        if not chosen:
            continue
        texts = [items[i] for i in pos]
        pages = len({b["page_number"] for b in texts})
        share = sum(b["n_chars"] for b in texts if b["selected"]) / max(1, sum(b["n_chars"] for b in texts))
        opens_with_arts = arts_topic in texts[0]["topics"] and texts[0]["text_type"] != "advert"
        if pages <= settings["max_pages"] and (opens_with_arts or share >= settings["whole_share"]):
            reason = "whole unit: opens with arts text" if opens_with_arts else "whole unit: mostly selected text"
            articles.append(_article(titles, items, pos[0], pos[-1], True, exclude, reason))
            continue
        why = f"selected part of a unit of {pages} pages" if pages > settings["max_pages"] else "selected part of a unit"
        for g, (a, z) in enumerate(group_positions(chosen, max_gap)):
            heading = titles if (g == 0 and a <= max_gap) else []
            if heading:
                a = 0  # take in the few unselected boxes between heading and text
            articles.append(_article(heading, items, pos[a], pos[z], False, exclude, why))
    return articles
