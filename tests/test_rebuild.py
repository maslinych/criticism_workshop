"""Tests for the article rebuild rule (src/ncse/rebuild.py, D-016), on small made-up issues."""

from ncse.rebuild import SEPARATOR, group_positions, heading_kind, rebuild_issue, units

ARTS = "arts"
SETTINGS = {"max_gap": 2, "max_pages": 3, "whole_share": 0.5, "exclude_classes": ["figure", "table"]}


def box(uid, cls="text", selected=False, page=1, content=None, topics=None, text_type="article", invented=None, n_chars=100):
    return {
        "bbox_uid": uid,
        "class": cls,
        "selected": selected,
        "page_number": page,
        "issue_date": "1851-09-27",
        "content": content if content is not None else f"text of {uid}",
        "topics": topics if topics is not None else ([ARTS] if selected else ["politics"]),
        "text_type": text_type,
        "invented": invented,
        "n_chars": n_chars,
    }


def uids(article):
    return [b["bbox_uid"] for b in article.boxes]


def rebuild(boxes, **changes):
    return rebuild_issue(boxes, {**SETTINGS, **changes}, ARTS)


# --- headings and units ---------------------------------------------------

def test_heading_kinds():
    assert heading_kind(box("t", "title")) == "title box"
    assert heading_kind(box("a", content="HEINE'S POEMS. Pictures of Travel.")) == "heading in capitals"
    assert heading_kind(box("a", content="Art. VI.—A Practical Exposition of the Law")) == "numbered review"
    assert heading_kind(box("a", content="Christian Theology. By John Calvin. London: Hunter. 8vo. pp. 460.")) == "book heading"
    assert heading_kind(box("a", content="THE LEADER. [No. 438, August 14, 1858.")) is None  # running page header
    assert heading_kind(box("a", content="Tims is not, as its title seems to indicate, a History")) is None
    assert heading_kind(box("a", content="the work by Mr. Smith, 8vo., which we noticed")) is None  # starts mid-sentence
    assert heading_kind(box("f", "figure", content="HEINE'S POEMS.")) is None


def test_units_split_at_headings_and_keep_titles_with_following_heading():
    boxes = [box("a"), box("T1", "title"), box("H", content="REED ON ENGLISH LITERATURE. By Henry Reed."),
             box("b"), box("H2", content="HEINE'S POEMS. Pictures."), box("c")]
    assert [[b["bbox_uid"] for b in u] for u in units(boxes)] == [["a"], ["T1", "H", "b"], ["H2", "c"]]


def test_group_positions():
    assert group_positions([0, 1, 4, 8], max_gap=2) == [(0, 4), (8, 8)]
    assert group_positions([0, 3], max_gap=2) == [(0, 3)]
    assert group_positions([0, 4], max_gap=2) == [(0, 0), (4, 4)]


# --- whole units ----------------------------------------------------------

def test_unit_without_selected_box_gives_no_article():
    assert rebuild([box("T", "title"), box("a", topics=[ARTS]), box("b")]) == []


def test_unit_opening_with_arts_text_is_taken_whole():
    # The first box has the arts topic but is typed "poem/song/story", so it is not selected;
    # a later box is selected. The whole review is taken.
    boxes = [box("T", "title"), box("a", topics=[ARTS], text_type="poem/song/story"), box("b"),
             box("c", selected=True), box("d"), box("e"), box("f")]
    [art] = rebuild(boxes)
    assert art.whole
    assert uids(art) == ["T", "a", "b", "c", "d", "e", "f"]
    assert art.notes[0] == "whole unit: opens with arts text"


def test_unit_with_mostly_selected_text_is_taken_whole():
    boxes = [box("T", "title"), box("a"), box("b", selected=True, n_chars=300)]
    [art] = rebuild(boxes)
    assert art.whole and uids(art) == ["T", "a", "b"]
    assert art.notes[0] == "whole unit: mostly selected text"


def test_advert_does_not_open_a_unit_with_arts_text():
    boxes = [box("T", "title"), box("ad", topics=[ARTS], text_type="advert", n_chars=1000), box("x"), box("y"),
             box("z"), box("s", selected=True)]
    [art] = rebuild(boxes)
    assert not art.whole and uids(art) == ["s"]


def test_long_unit_is_not_taken_whole():
    boxes = [box("T", "title"), box("a", selected=True, page=1)] + [box(f"x{i}", page=i) for i in range(2, 6)]
    [art] = rebuild(boxes)
    assert not art.whole
    assert uids(art) == ["T", "a"]
    assert art.notes[0] == "selected part of a unit of 5 pages"


# --- selected parts (as under D-012) ---------------------------------------

def test_long_gap_splits_articles_and_only_first_gets_heading():
    # The unit opens with non-arts text and is mostly unselected, so only selected parts are taken.
    boxes = [box("T", "title"), box("p"), box("a", selected=True)] + [box(f"x{i}") for i in range(3)] + [box("b", selected=True)]
    first, second = rebuild(boxes)
    assert not first.whole
    assert uids(first) == ["T", "p", "a"]
    assert uids(second) == ["b"]
    assert "no heading" in second.notes


def test_heading_far_from_selected_text_is_not_attached():
    boxes = [box("T", "title")] + [box(f"x{i}") for i in range(3)] + [box("a", selected=True)]
    [art] = rebuild(boxes)
    assert uids(art) == ["a"]


def test_heading_close_to_selected_text_takes_in_boxes_between():
    boxes = [box("T", "title"), box("x", n_chars=100), box("y", n_chars=100), box("a", selected=True, n_chars=50)]
    [art] = rebuild(boxes)
    assert not art.whole and uids(art) == ["T", "x", "y", "a"]
    assert any(n.startswith("includes 2 unselected") for n in art.notes)


def test_article_starting_at_heading_in_text_is_noted():
    [art] = rebuild([box("H", selected=True, content="THE OPERAS. Operas this season")])
    assert "starts at a heading in capitals" in art.notes


# --- boxes left out ---------------------------------------------------------

def test_figures_and_tables_are_left_out_and_noted():
    boxes = [box("a", selected=True), box("F", "figure", selected=True), box("b", selected=True)]
    [art] = rebuild(boxes, max_gap=0)
    assert uids(art) == ["a", "b"]
    assert any("F" in n and n.startswith("omitted") for n in art.notes)


def test_invented_text_is_left_out_noted_and_cannot_start_an_article():
    boxes = [box("a", selected=True), box("I", selected=True, invented="loop"), box("b", selected=True),
             box("T", "title"), box("I2", selected=True, invented="loop")]
    [art] = rebuild(boxes)
    assert uids(art) == ["a", "b"]
    assert [b["bbox_uid"] for b in art.left_out] == ["I"]
    assert any(n.startswith("left out invented text") and "I" in n for n in art.notes)


def test_year_later_than_issue_is_flagged_but_kept():
    boxes = [box("a", selected=True, content="Mr. Trelawny's Life of Byron (1858) is a work"),
             box("b", selected=True, content="In 1852 the Exhibition will reopen")]
    [art] = rebuild(boxes)
    assert uids(art) == ["a", "b"]
    assert "mentions a year later than the issue: a (1858)" in art.notes


def test_page_break_is_noted():
    [art] = rebuild([box("a", selected=True, page=1), box("b", selected=True, page=2)])
    assert "crosses page break" in art.notes


def test_text_is_box_contents_unchanged():
    raw = ["  Mr. Dickens's new  work\n", "is ADMIRABLE;\n\n  indeed  "]
    boxes = [box("a", selected=True, content=raw[0]), box("b", selected=True, content=raw[1])]
    [art] = rebuild(boxes)
    assert art.text == SEPARATOR.join(raw)


def test_every_box_used_at_most_once():
    boxes = [box("T", "title"), box("a", selected=True), box("b"), box("c"), box("d"), box("e", selected=True),
             box("T2", "title"), box("f", selected=True), box("H", content="NEW NOVELS. By Mr. Smith"), box("g", selected=True)]
    arts = rebuild(boxes)
    all_ids = [u for a in arts for u in uids(a)]
    assert len(all_ids) == len(set(all_ids))
