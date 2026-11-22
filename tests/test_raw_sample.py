"""Stages 2–3 on the raw NCSE sample (raw_sample/, D-021): no download needed.

The raw sample holds every NCSE box on the pages of a dozen articles. Loading it
with the real code (source.py) and rebuilding articles (rebuild.py, prepare.py)
must give exactly the articles listed in raw_sample/articles.csv: the same NCSE
boxes, the same notes and the same text as from the full data.
"""

import csv

from ncse.config import load_config
from ncse.rawsample import check
from ncse.runlog import RunLog
from ncse.source import load_boxes

CFG = load_config()
SAMPLE = CFG["paths"]["raw_sample"]


def test_articles_are_rebuilt_exactly(tmp_path):
    log = RunLog("test-raw-sample", tmp_path)
    assert check(CFG, SAMPLE, log) >= 10
    log.close()


def test_sample_covers_every_kind_of_article():
    with open(SAMPLE / "articles.csv", encoding="utf-8", newline="") as f:
        kinds = {(r["periodical"], r["kind"]) for r in csv.DictReader(f)}
    for periodical in CFG["periodicals"]:
        for kind in ("whole unit", "selected part", "invented text left out"):
            assert (periodical["name"], kind) in kinds


def test_labels_join_one_to_one_and_pages_are_complete():
    sample_cfg = {**CFG, "paths": {**CFG["paths"], "raw": SAMPLE}}
    for periodical in CFG["periodicals"]:
        boxes = load_boxes(sample_cfg, periodical)  # raises if labels do not join one to one
        # every page is complete: reading order runs without gaps from its first box
        for (_, _), page in boxes.group_by(["issue_id", "page_number"]):
            order = sorted(page["reading_order"].to_list())
            assert order == list(range(order[0], order[0] + len(order)))
