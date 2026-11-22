"""Draw the raw NCSE sample (decisions D-008, D-021).

`uv run ncse sample-raw` writes raw_sample/: a small copy of the original NCSE
v2.0 rows, enough to rebuild about a dozen complete articles with the real
stage 2–3 code, without the 1 GB download. It is used by the tests and for
reading what the source data looks like.

How it is drawn:
1. The articles are rebuilt from the full downloaded data, as `ncse prepare` does.
2. For each periodical, articles are chosen at random (seed in config.yaml):
   some taken as whole units, some as selected parts of a unit, and one from
   which a box of invented text was left out, so that every path of the rebuild
   rule is covered. Only articles whose unit spans at most `max_pages` pages
   are eligible, to keep the sample small.
3. For each chosen article, *every* box on the pages its unit spans is copied
   (all classes, selected or not), with its rows from the two label tables.
   Because the unit lies wholly on these pages, the article comes out of the
   sample exactly as it comes out of the full data.
4. The files are written as plain CSV in the same folder layout as the NCSE
   download (`.csv` instead of `.parquet`), with the two class mapping files.
   `articles.csv` lists the chosen articles and what the rebuild must give.
5. The sample is rebuilt at once and checked against `articles.csv`.
"""

import csv
import hashlib
import random
import shutil
from pathlib import Path

import polars as pl

from .prepare import article_rows
from .rebuild import units
from .runlog import RunLog
from .source import load_boxes

LABEL_TABLES = ("text_type_classified", "IPTC_type_classified")

ARTICLE_COLUMNS = {
    "article_id": "identifier of the article in the full corpus (the running number differs in the sample)",
    "periodical": "periodical title",
    "kind": "why it was chosen: whole unit, selected part, or invented text left out",
    "pages": "pages copied into the sample for this article (the pages its unit spans), separated by ';'",
    "whole_unit": "as in metadata.csv",
    "ncse_entry_ids": "as in metadata.csv: the boxes the article must be rebuilt from",
    "rebuild_notes": "as in metadata.csv",
    "text_sha256": "SHA-256 checksum of the article text, to check that the sample gives the same text",
}


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def unit_pages(issue_boxes: list[dict], entry_ids: list[str]) -> list[int]:
    """Pages spanned by the unit that holds the article's boxes."""
    first = entry_ids[-1]  # the last box is never a title box, so it is inside the unit body
    for u in units(issue_boxes):
        if any(b["bbox_uid"] == first for b in u):
            return sorted({b["page_number"] for b in u})
    raise ValueError(f"box {first} not found in any unit")


def choose(rows: list[tuple[dict, str]], pages_of: dict[str, list[int]], settings: dict, rng: random.Random) -> list[tuple[dict, str, str]]:
    """Choose articles of each kind; returns (row, text, kind)."""
    eligible = [(r, t) for r, t in rows if len(pages_of[r["article_id"]]) <= settings["max_pages"]]
    kinds = [
        ("invented text left out", lambda r: "left out invented text" in r["rebuild_notes"], settings["invented"]),
        ("whole unit", lambda r: r["whole_unit"] == "yes", settings["whole"]),
        ("selected part", lambda r: r["whole_unit"] == "no", settings["part"]),
    ]
    chosen, used_pages = [], set()
    for kind, test, n in kinds:
        pool = [(r, t) for r, t in eligible if test(r) and r["article_id"] not in {c[0]["article_id"] for c in chosen}]
        rng.shuffle(pool)
        for r, t in pool:
            if len([c for c in chosen if c[2] == kind]) >= n:
                break
            key = {(r["issue_id"], p) for p in pages_of[r["article_id"]]}
            if key & used_pages:  # keep the chosen articles on separate pages
                continue
            chosen.append((r, t, kind))
            used_pages |= key
    return chosen


def write_rows(cfg: dict, periodical: dict, pages: set[tuple[str, int]], out: Path) -> int:
    """Copy all rows of the given (issue, page) pairs from the three NCSE tables as CSV."""
    raw: Path = cfg["paths"]["raw"]
    name = periodical["file"]
    boxes = pl.read_parquet(raw / "NCSE_v2" / "post_processed" / f"{name}_issue_PDF_files.parquet")
    keep = pl.DataFrame({"issue_id": [i for i, _ in pages], "page_number": [p for _, p in pages]},
                        schema={"issue_id": pl.String, "page_number": boxes.schema["page_number"]})
    boxes = boxes.join(keep, on=["issue_id", "page_number"], how="semi").sort("issue_id", "page_number", "reading_order")
    uids = (boxes["page_id"] + "_" + boxes["box_page_id"]).to_list()
    target = out / "NCSE_v2" / "post_processed"
    target.mkdir(parents=True, exist_ok=True)
    boxes.write_csv(target / f"{name}_issue_PDF_files.csv")
    for table in LABEL_TABLES:
        labels = pl.read_parquet(raw / "classification_data" / table / f"classified_{name}_issue_PDF_files.parquet")
        labels = labels.filter(pl.col("bbox_uid").is_in(uids)).sort("bbox_uid")
        target = out / "classification_data" / table
        target.mkdir(parents=True, exist_ok=True)
        labels.write_csv(target / f"classified_{name}_issue_PDF_files.csv")
    return boxes.height


def check(cfg: dict, folder: Path, log: RunLog) -> int:
    """Rebuild articles from the sample and compare them with articles.csv. Returns the number checked."""
    with open(folder / "articles.csv", encoding="utf-8", newline="") as f:
        expected = list(csv.DictReader(f))
    sample_cfg = {**cfg, "paths": {**cfg["paths"], "raw": folder}}
    rebuilt = {}
    for periodical in cfg["periodicals"]:
        rows, _ = article_rows(sample_cfg, periodical, log)
        rebuilt.update({r["ncse_entry_ids"]: (r, t) for r, t in rows})
    for e in expected:
        if e["ncse_entry_ids"] not in rebuilt:
            raise AssertionError(f"{e['article_id']} is not rebuilt from the raw sample")
        r, t = rebuilt[e["ncse_entry_ids"]]
        for col in ("whole_unit", "rebuild_notes"):
            if r[col] != e[col]:
                raise AssertionError(f"{e['article_id']}: {col} differs: {r[col]!r} != {e[col]!r}")
        if text_sha256(t) != e["text_sha256"]:
            raise AssertionError(f"{e['article_id']}: text differs")
    return len(expected)


def readme(cfg: dict, chosen: list[tuple[dict, str, str]], n_boxes: dict[str, int]) -> str:
    src = cfg["source"]
    rows = "\n".join(
        f"| {r['article_id']} | {kind} | {';'.join(map(str, p))} | {r['n_words']} | {' '.join(r['heading'].split())[:50].replace('|', '/') or '—'} |"
        for r, _, kind, p in chosen
    )
    s = cfg["raw_sample"]
    return f"""# Raw NCSE sample

A small copy of the **original NCSE v2.0 data**: every box (text, title, figure and table) on {sum(len(c[3]) for c in chosen)} pages, {sum(n_boxes.values())} boxes in all ({', '.join(f'{k}: {v}' for k, v in n_boxes.items())}), with their rows from the two label tables. It holds {len(chosen)} complete articles and is enough to run the selection and article-rebuilding code (stages 2–3) without the 1 GB download. The tests rebuild the articles from it and compare them with `articles.csv`.

Made by `uv run ncse sample-raw` (code: `src/ncse/rawsample.py`, decision D-021). Do not edit by hand.

## How it was drawn

For each periodical, articles were chosen at random (seed {s['seed']}) from those whose unit spans at most {s['max_pages']} pages: {s['whole']} taken as whole units, {s['part']} taken as selected parts of a longer unit, and {s['invented']} from which a box of invented OCR text was left out. For each chosen article, all boxes on the pages of its unit were copied, so the article comes out of the sample exactly as out of the full data. Other articles on the same pages are rebuilt too, but they may be cut off at the edge of the copied pages.

| Article (full corpus) | Chosen as | Pages copied | Words | Heading |
|---|---|---|---:|---|
{rows}

## Files

The layout is the same as the NCSE download, with plain CSV files (UTF-8, comma-separated) instead of parquet:

- `NCSE_v2/post_processed/<periodical>_issue_PDF_files.csv`: one row per box: issue, page, place in the reading order, box class, OCR text (`content`), and the OCR model's token counts.
- `classification_data/text_type_classified/classified_<periodical>_issue_PDF_files.csv`: the text type label of each box (`predicted_class`, see `class_mappings/text_type_class_mapping.json`).
- `classification_data/IPTC_type_classified/classified_<periodical>_issue_PDF_files.csv`: the topic labels of each box (`class_<k>` = 1 when topic k applies, see `class_mappings/IPTC_class_mapping.json`).
- `class_mappings/`: the names of the label codes, copied unchanged.
- `articles.csv`: the chosen articles and what the rebuild must give for them.

To run the code on the sample, set `paths.raw` in `config.yaml` to `raw_sample`, or do as `tests/test_raw_sample.py` does.

## Source and licence

The data comes from **NCSE v2.0**: {src['author']} ({src['year']}), *{src['title']}*, University College London, <https://doi.org/{src['doi']}>, licensed under {src['licence']}. That edition is based on the **Nineteenth-Century Serials Edition (NCSE, 2008; <https://ncse.ac.uk>)**. This sample is an unchanged extract (converted from parquet to CSV) and is shared under the same licence, {src['licence']}.
"""


def run(cfg: dict) -> None:
    log = RunLog("sample-raw", cfg["paths"]["logs"])
    settings = cfg["raw_sample"]
    out: Path = cfg["paths"]["raw_sample"]
    rng = random.Random(settings["seed"])
    tmp = out.with_name(out.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)

    chosen_all, n_boxes = [], {}
    for periodical in cfg["periodicals"]:
        rows, _ = article_rows(cfg, periodical, log)
        boxes = load_boxes(cfg, periodical)
        by_issue = {i: g.to_dicts() for (i,), g in boxes.group_by(["issue_id"])}
        pages_of = {r["article_id"]: unit_pages(by_issue[r["issue_id"]], r["ncse_entry_ids"].split(";")) for r, _ in rows}
        chosen = choose(rows, pages_of, settings, rng)
        chosen_all += [(r, t, kind, pages_of[r["article_id"]]) for r, t, kind in chosen]
        pages = {(r["issue_id"], p) for r, _, _ in chosen for p in pages_of[r["article_id"]]}
        n_boxes[periodical["name"]] = write_rows(cfg, periodical, pages, tmp)
        log.info(f"{periodical['name']}: {len(chosen)} articles, {len(pages)} pages, {n_boxes[periodical['name']]} boxes")
        log.count("articles chosen", len(chosen))
        log.count("boxes copied", n_boxes[periodical["name"]])

    shutil.copytree(cfg["paths"]["raw"] / "class_mappings", tmp / "class_mappings")
    chosen_all.sort(key=lambda c: c[0]["article_id"])
    with open(tmp / "articles.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(ARTICLE_COLUMNS))
        w.writeheader()
        for r, t, kind, p in chosen_all:
            w.writerow({"article_id": r["article_id"], "periodical": r["periodical"], "kind": kind,
                        "pages": ";".join(map(str, p)), "whole_unit": r["whole_unit"],
                        "ncse_entry_ids": r["ncse_entry_ids"], "rebuild_notes": r["rebuild_notes"],
                        "text_sha256": text_sha256(t)})
    (tmp / "README.md").write_text(readme(cfg, chosen_all, n_boxes), encoding="utf-8")

    n = check(cfg, tmp, log)
    log.info(f"checked: all {n} articles are rebuilt from the sample exactly as from the full data")
    shutil.rmtree(out, ignore_errors=True)
    tmp.rename(out)
    log.info(f"raw sample written to {out}")
    log.close()
