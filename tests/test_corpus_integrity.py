"""Integrity checks for the prepared corpus.

Run on the committed sample corpus (corpus_sample/) always, and on the full
corpus (data/corpus/full/) when it has been built. The last test checks every
sample article against the original NCSE files, when they have been downloaded.
"""

import csv
from pathlib import Path

import pytest

from ncse.config import load_config
from ncse.prepare import METADATA_COLUMNS
from ncse.rebuild import SEPARATOR

CFG = load_config()
REQUIRED = ["article_id", "file_name", "periodical", "issue_id", "issue_date", "pages",
            "n_words", "n_chars", "n_entries", "ncse_text_types", "ncse_topics", "ncse_entry_ids"]

corpora = [CFG["paths"]["corpus_sample"]]
if (CFG["paths"]["corpus"] / "metadata.csv").exists():
    corpora.append(CFG["paths"]["corpus"])


def read_metadata(folder: Path) -> list[dict]:
    with open(folder / "metadata.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(params=corpora, ids=[c.name for c in corpora])
def corpus(request):
    folder = request.param
    return folder, read_metadata(folder)


def test_columns(corpus):
    folder, rows = corpus
    assert rows, "metadata.csv is empty"
    assert list(rows[0]) == list(METADATA_COLUMNS)


def test_ids_unique_and_match_file_names(corpus):
    _, rows = corpus
    ids = [r["article_id"] for r in rows]
    assert len(ids) == len(set(ids))
    assert all(r["file_name"] == r["article_id"] + ".txt" for r in rows)


def test_one_text_file_per_row_and_back(corpus):
    folder, rows = corpus
    files = {p.name for p in (folder / "texts").iterdir()}
    assert files == {r["file_name"] for r in rows}


def test_required_fields_filled(corpus):
    _, rows = corpus
    for r in rows:
        empty = [c for c in REQUIRED if not r[c]]
        assert not empty, f"{r['article_id']}: empty {empty}"


def test_texts_nonempty_and_lengths_match(corpus):
    folder, rows = corpus
    for r in rows:
        text = (folder / "texts" / r["file_name"]).read_text(encoding="utf-8")
        assert text.strip(), r["article_id"]
        assert len(text) == int(r["n_chars"]), r["article_id"]
        assert len(text.split()) == int(r["n_words"]), r["article_id"]


def test_entry_lists_consistent(corpus):
    _, rows = corpus
    seen = set()
    for r in rows:
        entries = r["ncse_entry_ids"].split(";")
        assert len(entries) == int(r["n_entries"])
        assert len(r["ncse_text_types"].split(";")) == len(entries)
        assert len(r["ncse_topics"].split(";")) == len(entries)
        assert all(e.startswith(r["issue_id"] + "_page_") for e in entries)
        assert not seen & set(entries), f"{r['article_id']} reuses an NCSE entry"
        seen |= set(entries)


RAW = CFG["paths"]["raw"] / "NCSE_v2"


@pytest.mark.skipif(not RAW.exists(), reason="NCSE source files not downloaded")
def test_sample_texts_match_source():
    """Rebuild each sample article's text directly from the NCSE files and compare."""
    import polars as pl

    folder = CFG["paths"]["corpus_sample"]
    rows = read_metadata(folder)
    for periodical in CFG["periodicals"]:
        boxes = pl.read_parquet(RAW / "post_processed" / f"{periodical['file']}_issue_PDF_files.parquet")
        content = dict(
            zip((boxes["page_id"] + "_" + boxes["box_page_id"]).to_list(), boxes["content"].to_list())
        )
        for r in rows:
            if r["periodical"] != periodical["name"]:
                continue
            expected = SEPARATOR.join(content[e] for e in r["ncse_entry_ids"].split(";"))
            assert (folder / "texts" / r["file_name"]).read_text(encoding="utf-8") == expected
