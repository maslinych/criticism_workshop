"""Tests for the article rebuild rule (src/ncse/rebuild.py), on small made-up issues."""

from ncse.rebuild import SEPARATOR, group_positions, rebuild_issue, segments

EXCLUDE = {"figure", "table"}


def box(uid, cls="text", selected=False, page=1, content=None):
    return {
        "bbox_uid": uid,
        "class": cls,
        "selected": selected,
        "page_number": page,
        "content": content if content is not None else f"text of {uid}",
    }


def uids(article):
    return [b["bbox_uid"] for b in article.boxes]


def test_segments_split_at_titles_and_group_consecutive_titles():
    boxes = [box("a"), box("T1", "title"), box("T2", "title"), box("b"), box("T3", "title"), box("c")]
    result = segments(boxes)
    assert [[b["bbox_uid"] for b in t] for t, _ in result] == [[], ["T1", "T2"], ["T3"]]
    assert [[b["bbox_uid"] for b in i] for _, i in result] == [["a"], ["b"], ["c"]]


def test_group_positions():
    assert group_positions([0, 1, 4, 8], max_gap=2) == [(0, 4), (8, 8)]
    assert group_positions([0, 3], max_gap=2) == [(0, 3)]
    assert group_positions([0, 4], max_gap=2) == [(0, 0), (4, 4)]


def test_unselected_segment_gives_no_article():
    assert rebuild_issue([box("T", "title"), box("a"), box("b")], 2, EXCLUDE) == []


def test_heading_is_attached_and_gap_is_bridged():
    boxes = [box("T", "title"), box("a", selected=True), box("b"), box("c", selected=True), box("d")]
    [art] = rebuild_issue(boxes, 2, EXCLUDE)
    assert uids(art) == ["T", "a", "b", "c"]
    assert art.heading_count == 1
    assert any(n.startswith("bridged 1") for n in art.notes)


def test_long_gap_splits_articles_and_only_first_gets_heading():
    boxes = [box("T", "title"), box("a", selected=True)] + [box(f"x{i}") for i in range(3)] + [box("b", selected=True)]
    first, second = rebuild_issue(boxes, 2, EXCLUDE)
    assert uids(first) == ["T", "a"]
    assert uids(second) == ["b"]
    assert "no heading" in second.notes


def test_heading_far_from_selected_text_is_not_attached():
    boxes = [box("T", "title")] + [box(f"x{i}") for i in range(3)] + [box("a", selected=True)]
    [art] = rebuild_issue(boxes, 2, EXCLUDE)
    assert uids(art) == ["a"]


def test_heading_close_to_selected_text_takes_in_boxes_between():
    boxes = [box("T", "title"), box("x"), box("a", selected=True)]
    [art] = rebuild_issue(boxes, 2, EXCLUDE)
    assert uids(art) == ["T", "x", "a"]


def test_figures_and_tables_are_left_out_and_noted():
    boxes = [box("a", selected=True), box("F", "figure", selected=True), box("b", selected=True)]
    [art] = rebuild_issue(boxes, 0, EXCLUDE)
    assert uids(art) == ["a", "b"]
    assert any("F" in n and n.startswith("omitted") for n in art.notes)


def test_page_break_is_noted():
    [art] = rebuild_issue([box("a", selected=True, page=1), box("b", selected=True, page=2)], 2, EXCLUDE)
    assert "crosses page break" in art.notes


def test_text_is_box_contents_unchanged():
    raw = ["  Mr. Dickens's new  work\n", "is ADMIRABLE;\n\n  indeed  "]
    boxes = [box("a", selected=True, content=raw[0]), box("b", selected=True, content=raw[1])]
    [art] = rebuild_issue(boxes, 2, EXCLUDE)
    assert art.text == SEPARATOR.join(raw)


def test_every_box_used_at_most_once():
    boxes = [box("T", "title"), box("a", selected=True), box("b"), box("c"), box("d"), box("e", selected=True),
             box("T2", "title"), box("f", selected=True)]
    arts = rebuild_issue(boxes, 2, EXCLUDE)
    all_ids = [u for a in arts for u in uids(a)]
    assert len(all_ids) == len(set(all_ids))
