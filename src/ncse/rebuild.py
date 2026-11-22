"""Rebuild articles from NCSE boxes (decision D-012, provisional).

NCSE boxes are smaller than articles, and their labels are assigned box by box,
so a single review is often labelled "arts" in one box and something else in
the next. The rule used here:

1. Take one issue's boxes in reading order (page, then reading order on the page).
   Leave out figure and table boxes (D-013); they are noted when they fall inside
   an article.
2. Split the issue into *segments* at title boxes. A run of consecutive title
   boxes forms the heading of the segment that follows it.
3. Inside a segment, find the text boxes that meet the selection rule (D-002).
   Selected boxes separated by at most `max_gap` unselected boxes belong to the
   same article; the unselected boxes between them are included ("bridged").
4. The segment heading is attached to the first article of the segment if that
   article starts within `max_gap` boxes of the heading.

The functions here work on plain Python dictionaries, so they can be tested
without the real data. Text is never changed: the article text is the box texts
joined with a blank line.
"""

from dataclasses import dataclass, field

SEPARATOR = "\n\n"


@dataclass
class Article:
    boxes: list[dict]          # title boxes first, then text boxes, in reading order
    heading_count: int         # how many of the boxes are heading (title) boxes
    notes: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return SEPARATOR.join(b["content"] for b in self.boxes)

    @property
    def heading(self) -> str:
        return " | ".join(" ".join(b["content"].split()) for b in self.boxes[: self.heading_count])


def segments(boxes: list[dict]) -> list[tuple[list[dict], list[dict]]]:
    """Split an issue's boxes into (titles, items) segments.

    A segment is a run of title boxes followed by the non-title boxes up to the
    next title. `items` keeps excluded boxes (figures, tables) in place so that
    they can be noted.
    """
    result, titles, items = [], [], []
    for box in boxes:
        if box["class"] == "title":
            if items:  # a title after body text starts a new segment
                result.append((titles, items))
                titles, items = [], []
            titles.append(box)
        else:
            items.append(box)
    if titles or items:
        result.append((titles, items))
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


def rebuild_issue(boxes: list[dict], max_gap: int, exclude_classes: set[str]) -> list[Article]:
    """Build the selected articles of one issue. `boxes` must be in reading order."""
    articles: list[Article] = []
    for titles, items in segments(boxes):
        # Positions (in `items`) of the boxes that can go into the text.
        usable = [i for i, b in enumerate(items) if b["class"] not in exclude_classes]
        chosen = [k for k, i in enumerate(usable) if items[usable[k]]["selected"]]
        if not chosen:
            continue
        for g, (first, last) in enumerate(group_positions(chosen, max_gap)):
            heading = titles if (g == 0 and first <= max_gap) else []
            if heading:
                first = 0  # take in the few unselected boxes between heading and text
            body = [items[i] for i in usable[first : last + 1]]
            notes = []
            if not heading:
                notes.append("no heading")
            bridged = [b["bbox_uid"] for b in body if not b["selected"]]
            if bridged:
                notes.append(f"bridged {len(bridged)} unselected box(es): {' '.join(bridged)}")
            span = items[usable[first] : usable[last] + 1]
            omitted = [b["bbox_uid"] for b in span if b["class"] in exclude_classes]
            if omitted:
                notes.append(f"omitted figure/table box(es): {' '.join(omitted)}")
            if len({b["page_number"] for b in heading + body}) > 1:
                notes.append("crosses page break")
            articles.append(Article(boxes=heading + body, heading_count=len(heading), notes=notes))
    return articles
