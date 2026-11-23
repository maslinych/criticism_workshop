"""Tests for stage 8 (assembling the dataset) and stage 9 (statistics).

The first tests build annotation records with a fake LLM (as in
test_annotate.py), assemble them and check the tables. The integrity tests at
the end run on every dataset already assembled under data/dataset/ (AGENTS.md,
section 7): unique identifiers, every statement linked to an article, only
allowed values, no empty required fields, quotations that are exact slices of
the article text.
"""

import csv
import hashlib
import json
from pathlib import Path

import pytest
from test_annotate import ARTICLE, QUOTE, FakeClient, good_answer

from ncse import annotate, dataset, stats
from ncse.config import PROJECT_ROOT, load_config

CFG = load_config()


@pytest.fixture
def cfg(tmp_path):
    cfg = load_config()
    for key in ("annotation", "logs", "reports", "dataset"):
        cfg["paths"][key] = tmp_path / key
    cfg["paths"]["reports"].mkdir()
    for step in ("analyst", "reviewer"):
        cfg["annotation"][step]["model"] = "fake-model"
    cfg["annotation"]["concurrency"] = 1
    cfg["annotation"]["max_part_chars"] = None
    return cfg


def two_statements():
    """An analyst answer with two statements on one passage."""
    answer = json.loads(good_answer())
    st = answer["passages"][0]["statements"][0]
    second = {**st, "evaluative_expression": "familiar as household words",
              "criterion": {"value": "tradition", "evidence": "inferred", "assumption": "familiarity as heritage"}}
    answer["passages"][0]["statements"].append(second)
    return json.dumps(answer)


def review(*actions):
    return json.dumps({"actions": [dict(zip(("statement_id", "field", "action", "new_evidence", "reason"), a))
                                   for a in actions]})


def annotate_sample(cfg, analyst_answer, reviewer_answer):
    annotate.run(cfg, "analyst", sample=True, client=FakeClient([analyst_answer]), articles=[ARTICLE])
    annotate.run(cfg, "reviewer", sample=True, client=FakeClient([reviewer_answer]), articles=[ARTICLE])


def rows(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_assemble_statements_articles_and_dictionary(cfg):
    annotate_sample(cfg, two_statements(),
                    review(("p01-s02", "statement", "delete", None, "Not an evaluation."),
                           ("p01-s01", "work_genre", "downgrade", "inferred", "Genre not stated.")))
    out = dataset.run(cfg, sample=True)
    st = rows(out / "statements.csv")
    assert [c for c, _ in dataset.STATEMENT_COLUMNS] == list(st[0])
    assert [s["statement_id"] for s in st] == [f"{ARTICLE}-p01-s01", f"{ARTICLE}-p01-s02"]
    first, second = st
    # the deleted statement stays, marked, with the reason
    assert second["deleted"] == "yes" and second["deleted_reason"] == "Not an evaluation."
    assert first["deleted"] == "no"
    # a downgrade: level after review, the analyst's level, and the reason
    assert (first["work_genre_evidence"], first["work_genre_evidence_analyst"],
            first["work_genre_review"]) == ("inferred", "observed", "downgraded")
    assert first["evidence"] == "inferred" and first["evidence_analyst"] == "observed"
    # quotations and expressions are exact slices of the article text
    text = (CFG["paths"]["corpus_sample"] / "texts" / f"{ARTICLE}.txt").read_text(encoding="utf-8")
    for s in st:
        assert text[int(s["quote_start"]):int(s["quote_end"])] == s["quote"] == QUOTE
        assert text[int(s["expression_start"]):int(s["expression_end"])] == s["evaluative_expression"]
    # provenance
    assert first["analyst_model"] == "fake-model" and first["analyst_run_id"].startswith("analyst-")
    assert first["reviewer_run_id"].startswith("reviewer-") and first["corpus_version"] == "corpus-v1.0 sample"

    arts = rows(out / "articles.csv")
    sample_ids = [r["article_id"] for r in rows(CFG["paths"]["corpus_sample"] / "metadata.csv")]
    assert [a["article_id"] for a in arts] == sample_ids  # one row per corpus article
    mine = next(a for a in arts if a["article_id"] == ARTICLE)
    assert (mine["in_dataset"], mine["n_statements"], mine["n_deleted"]) == ("yes", "2", "1")
    assert all(a["in_dataset"] == "no" and a["analyst_status"] == "not processed"
               for a in arts if a["article_id"] != ARTICLE)

    runs = rows(out / "runs.csv")
    assert {r["step"] for r in runs} == {"analyst", "reviewer"} and all(r["used_in_dataset"] == "yes" for r in runs)
    info = json.loads((out / "ASSEMBLY.json").read_text())
    assert info["statements"] == 2 and info["statements_deleted"] == 1
    assert info["sha256"]["statements.csv"] == hashlib.sha256((out / "statements.csv").read_bytes()).hexdigest()
    assert (out / "DATA_DICTIONARY.md").read_text() == dataset.data_dictionary()


def test_outdated_review_is_left_out(cfg):
    annotate_sample(cfg, good_answer(), review())
    folder = annotate.output_folder(cfg, "analyst", True)
    rec = annotate.load_record(folder, ARTICLE)
    rec["result"]["passages"][0]["statements"][0]["note"] = "changed"  # the analyst result no longer matches
    annotate.save_record(folder, rec)
    out = dataset.run(cfg, sample=True)
    mine = next(a for a in rows(out / "articles.csv") if a["article_id"] == ARTICLE)
    assert mine["reviewer_status"] == "outdated" and mine["in_dataset"] == "no"
    assert rows(out / "statements.csv") == []


def test_failed_items_are_listed(cfg):
    unmatched = good_answer().replace("household words", "a story told by an idiot")
    annotate_sample(cfg, unmatched, review())
    out = dataset.run(cfg, sample=True)
    failed, = rows(out / "failed_items.csv")
    assert failed["article_id"] == ARTICLE and failed["item"] == "passage" and "does not match" in failed["reasons"]
    assert "a story told by an idiot" in failed["answer"]


def test_docs_dictionary_is_up_to_date():
    """docs/data-dictionary.md is a copy of what `ncse assemble` writes."""
    assert (PROJECT_ROOT / "docs" / "data-dictionary.md").read_text(encoding="utf-8") == dataset.data_dictionary()


# ---------------------------------------------------------------- statistics


def test_kappa_and_share_halfwidth():
    assert stats.kappa([("a", "a"), ("b", "b")]) == 1
    assert stats.kappa([("a", "b"), ("b", "a")]) == -1
    assert stats.share_halfwidth([(1, 2), (1, 2), (1, 2)]) == 0  # every article has the same share
    assert stats.share_halfwidth([(2, 2), (0, 2)]) == pytest.approx(1.96 * 0.5)  # var = 2 · 2 / 4²


def st(aid, start, end, **kw):
    base = {"article_id": aid, "expression_start": str(start), "expression_end": str(end), "creator": "",
            "work_title": "", "polarity": "positive", "criterion": "aesthetic value"}
    return {**base, **kw}


def test_matching_pairs_overlapping_expressions_one_to_one():
    a = [st("X", 0, 10, work_title="Emma"), st("X", 0, 10, work_title="Persuasion"), st("X", 50, 60),
         st("Y", 0, 5)]
    b = [st("X", 2, 12, work_title="Persuasion"), st("X", 0, 10, work_title="Emma"), st("X", 70, 80),
         st("Z", 0, 5)]
    pairs, only_a, only_b = stats.match_statements(a, b)
    assert {(x["work_title"], y["work_title"]) for x, y in pairs} == {("Emma", "Emma"), ("Persuasion", "Persuasion")}
    assert [s["expression_start"] for s in only_a] == ["50", "0"]
    assert [(s["article_id"], s["expression_start"]) for s in only_b] == [("X", "70"), ("Z", "0")]


def test_stats_report_for_one_and_two_runs(cfg):
    annotate_sample(cfg, two_statements(), review(("p01-s02", "statement", "delete", None, "Not an evaluation.")))
    out = dataset.run(cfg, sample=True)
    one = stats.run(cfg, sample=True).read_text()
    assert "statements kept | 1 |" in one and "comparison of runs" not in one
    two = stats.run(cfg, datasets=[str(out), str(out)], labels=["a", "b"], name="twice").read_text()
    assert "found by both (pairs) | 2 (100%)" in two
    assert "| criterion | 2 (100%) | 1.00 |" in two


# ---------------------------------------------------------------- integrity of assembled data

assembled = sorted(p.parent for p in CFG["paths"]["dataset"].glob("*/ASSEMBLY.json")) \
    if CFG["paths"]["dataset"].exists() else []


@pytest.mark.parametrize("folder", assembled, ids=[p.name for p in assembled])
def test_assembled_dataset_integrity(folder):
    statements, articles = rows(folder / "statements.csv"), rows(folder / "articles.csv")
    info = json.loads((folder / "ASSEMBLY.json").read_text())
    for name, digest in info["sha256"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == digest, f"{name} changed after assembly"
    ids = [s["statement_id"] for s in statements]
    assert len(ids) == len(set(ids))
    assert len({a["article_id"] for a in articles}) == len(articles)
    by_id = {a["article_id"]: a for a in articles}
    corpus = CFG["paths"]["corpus_sample" if info["corpus"] == "corpus_sample" else "corpus"]
    texts = {}
    required = ["statement_id", "passage_id", "article_id", "quote", "evaluative_expression", "art", "polarity",
                "sarcastic", "criterion", "evidence", "deleted", "analyst_model", "corpus_version"]
    for s in statements:
        art = by_id[s["article_id"]]
        assert art["in_dataset"] == "yes"
        assert s["statement_id"].startswith(s["passage_id"] + "-s") and s["passage_id"].startswith(s["article_id"])
        for col in required:
            assert s[col], f"{s['statement_id']}: {col} empty"
        for col in ("art", "polarity", "sarcastic", "criterion"):
            assert s[col] in dataset.CONTROLLED[col]
        for col in [c for c in s if c == "evidence" or c.endswith("_evidence") or c.endswith("_evidence_analyst")]:
            assert s[col] in ("", *dataset.LEVEL_VALUES)
        assert s["deleted"] in ("yes", "no") and (s["deleted"] == "yes") == bool(s["deleted_reason"])
        if s["article_id"] not in texts:
            texts[s["article_id"]] = (corpus / "texts" / f"{s['article_id']}.txt").read_text(encoding="utf-8")
        text = texts[s["article_id"]]
        assert text[int(s["quote_start"]):int(s["quote_end"])] == s["quote"]
        assert text[int(s["expression_start"]):int(s["expression_end"])] == s["evaluative_expression"]
        assert int(s["quote_start"]) <= int(s["expression_start"]) < int(s["expression_end"]) <= int(s["quote_end"])
    for a in articles:
        n = sum(1 for s in statements if s["article_id"] == a["article_id"])
        assert int(a["n_statements"]) == n
