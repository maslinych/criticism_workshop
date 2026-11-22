"""Stage 3: write the prepared corpus.

Output (for the full corpus in data/corpus/full/, and for the small sample in corpus_sample/):
  texts/<article_id>.txt   the article text: box texts joined by a blank line, OCR unchanged
  metadata.csv             one row per article (columns described in METADATA_COLUMNS)
  excluded_boxes.csv       boxes of text invented by the OCR model that were left out
                           (D-017; columns described in EXCLUDED_COLUMNS)
and a summary report in reports/02-corpus-summary.md.

Running the stage again rebuilds the corpus from scratch; the result is identical
as long as the source data and config.yaml are unchanged.
"""

import csv
import datetime as dt
import json
import re
import random
import shutil
from collections import Counter
from pathlib import Path

import polars as pl

from .rebuild import rebuild_issue
from .runlog import RunLog
from .source import load_boxes

METADATA_COLUMNS = {
    "article_id": "identifier: periodical code, issue date, running number in the issue",
    "file_name": "name of the text file in texts/",
    "periodical": "periodical title",
    "issue_id": "NCSE issue identifier",
    "issue_date": "issue date (YYYY-MM-DD) as given in the NCSE issue identifier",
    "pages": "page number(s) within the issue, separated by ';'",
    "heading": "text of the title box(es) heading the article, separated by ' | '; empty if none "
               "(a heading at the start of a text box stays in the text; see rebuild_notes)",
    "n_words": "number of words in the text file (split at whitespace)",
    "n_chars": "number of characters in the text file",
    "n_entries": "number of NCSE boxes the article was built from",
    "selected_share": "share of the article's characters in boxes that meet the selection rule",
    "whole_unit": "yes if the whole text from its heading to the next heading was taken; no if only the selected part (D-016)",
    "ncse_text_types": "NCSE text type label of each box, in order, separated by ';'",
    "ncse_topics": "NCSE topic labels of each box, in order, separated by ';' (several topics per box joined by '|')",
    "ncse_entry_ids": "NCSE box identifiers (bbox_uid) the article was built from, in reading order, separated by ';'",
    "rebuild_notes": "notes on how the article was rebuilt, separated by ' / '",
}

EXCLUDED_COLUMNS = {
    "ncse_entry_id": "NCSE box identifier (bbox_uid) of the box left out",
    "issue_id": "NCSE issue identifier",
    "page": "page number within the issue",
    "reason": "why the box counts as text invented by the OCR model (D-017)",
    "n_chars": "number of characters in the box",
    "selected": "yes if the box carries the labels of the selection rule (D-002)",
    "article_id": "the article the box lies inside, if any; empty if it would have formed or started an article on its own",
    "text_start": "the first 150 characters of the box, with spaces normalised (for reading only)",
}


def article_rows(cfg: dict, periodical: dict, log: RunLog) -> list[tuple[dict, str]]:
    boxes = load_boxes(cfg, periodical)
    log.info(f"{periodical['name']}: {boxes.height:,} boxes in {boxes['issue_id'].n_unique()} issues")
    log.count("boxes read", boxes.height)
    log.count("boxes meeting selection rule", int(boxes["selected"].sum()))
    inv = boxes.filter(pl.col("invented").is_not_null())
    log.info(f"  {inv.height:,} text/title boxes count as invented by the OCR model ({inv['n_chars'].sum():,} characters)")
    log.count("boxes of invented text", inv.height)
    log.count("boxes of invented text meeting selection rule", int(inv["selected"].sum()))
    rows, excluded = [], []
    for (issue_id,), issue in boxes.group_by(["issue_id"], maintain_order=True):
        issue_boxes = issue.to_dicts()
        articles = rebuild_issue(issue_boxes, cfg["rebuild"], cfg["selection"]["topic"])
        listed = set()
        for n, art in enumerate(articles, start=1):
            text = art.text
            article_id = f"{periodical['code']}-{art.boxes[0]['issue_date']}-{n:03d}"
            selected_chars = sum(b["n_chars"] for b in art.boxes if b["selected"])
            row = {
                "article_id": article_id,
                "file_name": f"{article_id}.txt",
                "periodical": periodical["name"],
                "issue_id": issue_id,
                "issue_date": art.boxes[0]["issue_date"],
                "pages": ";".join(str(p) for p in sorted({b["page_number"] for b in art.boxes})),
                "heading": art.heading,
                "n_words": len(text.split()),
                "n_chars": len(text),
                "n_entries": len(art.boxes),
                "selected_share": round(selected_chars / max(1, sum(b["n_chars"] for b in art.boxes)), 3),
                "whole_unit": "yes" if art.whole else "no",
                "ncse_text_types": ";".join(b["text_type"] for b in art.boxes),
                "ncse_topics": ";".join("|".join(b["topics"]) for b in art.boxes),
                "ncse_entry_ids": ";".join(b["bbox_uid"] for b in art.boxes),
                "rebuild_notes": " / ".join(art.notes),
                "_text_boxes": len(art.boxes) - art.heading_count,  # for the summary only, not written
            }
            rows.append((row, text))
            log.count("articles taken as whole units" if art.whole else "articles taken as selected parts of units")
            for note in art.notes:
                # count the kind of note, without the numbers and box identifiers
                log.count("note: " + re.sub(r"\d+ ", "", note.split(":")[0]))
            for b in art.left_out:
                if b["invented"]:
                    excluded.append(excluded_row(b, article_id))
                    listed.add(b["bbox_uid"])
        # Selected boxes of invented text that lie in no article are listed too.
        for b in issue_boxes:
            if b["invented"] and b["selected"] and b["bbox_uid"] not in listed:
                excluded.append(excluded_row(b, ""))
    log.info(f"  {len(rows):,} articles built; {len(excluded):,} boxes of invented text listed as excluded")
    log.count("articles built", len(rows))
    log.count("excluded boxes listed", len(excluded))
    return rows, excluded


def excluded_row(box: dict, article_id: str) -> dict:
    return {
        "ncse_entry_id": box["bbox_uid"],
        "issue_id": box["issue_id"],
        "page": box["page_number"],
        "reason": box["invented"],
        "n_chars": box["n_chars"],
        "selected": "yes" if box["selected"] else "no",
        "article_id": article_id,
        "text_start": " ".join(box["content"].split())[:150],
    }


def write_csv(path: Path, columns: dict, rows) -> None:
    tmp = path.with_suffix(".csv.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def write_corpus(rows: list[tuple[dict, str]], excluded: list[dict], folder: Path) -> None:
    """Write texts/, metadata.csv and excluded_boxes.csv into folder, replacing old versions safely."""
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / "texts.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    for row, text in rows:
        (tmp / row["file_name"]).write_text(text, encoding="utf-8", newline="")
    shutil.rmtree(folder / "texts", ignore_errors=True)
    tmp.rename(folder / "texts")
    write_csv(folder / "metadata.csv", METADATA_COLUMNS, (row for row, _ in rows))
    write_csv(folder / "excluded_boxes.csv", EXCLUDED_COLUMNS, excluded)


def choose_sample(rows: list[tuple[dict, str]], cfg: dict) -> list[tuple[dict, str]]:
    s = cfg["sample"]
    rng = random.Random(s["seed"])
    chosen = []
    for periodical in cfg["periodicals"]:
        pool = [r for r in rows if r[0]["periodical"] == periodical["name"] and r[0]["n_chars"] >= s["min_chars"]]
        chosen += rng.sample(pool, min(s["articles_per_periodical"], len(pool)))
    return sorted(chosen, key=lambda r: r[0]["article_id"])


def summary_report(rows: list[tuple[dict, str]], excluded: list[dict], counts: Counter) -> str:
    lines = [
        "# Prepared corpus: summary",
        "",
        "Generated by `uv run ncse prepare`. Do not edit by hand.",
        "",
        "## Articles per periodical",
        "",
        "| Periodical | Articles | Words | Median words | Whole units | With title box | Starting at a heading in the text "
        "| Starting without a heading | Crossing a page break | Only one text box |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    by_per: dict[str, list[dict]] = {}
    for row, _ in rows:
        by_per.setdefault(row["periodical"], []).append(row)
    for per, rs in by_per.items():
        words = sorted(r["n_words"] for r in rs)
        lines.append(
            f"| {per} | {len(rs):,} | {sum(words):,} | {words[len(words) // 2]:,} "
            f"| {sum(r['whole_unit'] == 'yes' for r in rs):,} | {sum(bool(r['heading']) for r in rs):,} "
            f"| {sum(' / starts at a ' in r['rebuild_notes'] for r in rs):,} "
            f"| {sum(' / no heading' in r['rebuild_notes'] for r in rs):,} "
            f"| {sum('crosses page break' in r['rebuild_notes'] for r in rs):,} "
            f"| {sum(r['_text_boxes'] == 1 for r in rs):,} |"
        )
    lines += [
        "",
        "## Boxes of invented text left out (D-017)",
        "",
        "Listed in `excluded_boxes.csv`: boxes inside an article, and selected boxes that would have formed an article.",
        "",
        "| Periodical | Boxes | Characters | Inside an article | Selected |",
        "|---|---:|---:|---:|---:|",
    ]
    for periodical in sorted(by_per):
        code = by_per[periodical][0]["article_id"][:3]
        ex = [e for e in excluded if e["issue_id"].startswith(code)]
        lines.append(
            f"| {periodical} | {len(ex):,} | {sum(e['n_chars'] for e in ex):,} "
            f"| {sum(bool(e['article_id']) for e in ex):,} | {sum(e['selected'] == 'yes' for e in ex):,} |"
        )
    reasons = Counter(e["reason"].split(":")[0] for e in excluded)
    lines += ["", "By test: " + "; ".join(f"{k}: {v:,}" for k, v in sorted(reasons.items())) + "."]
    lines += ["", "## Articles per decade", "", "| Periodical | Decade | Articles | Words |", "|---|---|---:|---:|"]
    dec = Counter()
    decw = Counter()
    for row, _ in rows:
        key = (row["periodical"], row["issue_date"][:3] + "0s")
        dec[key] += 1
        decw[key] += row["n_words"]
    for key in sorted(dec):
        lines.append(f"| {key[0]} | {key[1]} | {dec[key]:,} | {decw[key]:,} |")
    lines += ["", "## Length of articles (words)", "", "| Periodical | <100 | 100–499 | 500–1999 | 2000–4999 | ≥5000 |", "|---|---:|---:|---:|---:|---:|"]
    for per, rs in by_per.items():
        bins = Counter()
        for r in rs:
            w = r["n_words"]
            bins[0 if w < 100 else 1 if w < 500 else 2 if w < 2000 else 3 if w < 5000 else 4] += 1
        lines.append(f"| {per} | " + " | ".join(f"{bins[i]:,}" for i in range(5)) + " |")
    lines += ["", "## Run counts", ""] + [f"- {k}: {v:,}" for k, v in sorted(counts.items())]
    return "\n".join(lines) + "\n"


def run(cfg: dict) -> None:
    log = RunLog("prepare", cfg["paths"]["logs"])
    rows, excluded = [], []
    for periodical in cfg["periodicals"]:
        r, e = article_rows(cfg, periodical, log)
        rows += r
        excluded += e

    write_corpus(rows, excluded, cfg["paths"]["corpus"])
    # Provenance of the full corpus: which code built it (checked by `ncse package`).
    from .release import git_state

    build = {**git_state(), "built": dt.datetime.now().isoformat(timespec="seconds"), "articles": len(rows)}
    (cfg["paths"]["corpus"] / "BUILD.json").write_text(json.dumps(build, indent=2) + "\n")
    (cfg["paths"]["corpus"] / "FETCHED.json").unlink(missing_ok=True)  # now built locally, not fetched
    log.info(f"full corpus written to {cfg['paths']['corpus']} (commit {build['commit'][:10]}"
             f"{', with uncommitted changes' if build['dirty'] else ''})")
    sample = choose_sample(rows, cfg)
    sample_ids = {row["article_id"] for row, _ in sample}
    write_corpus(sample, [e for e in excluded if e["article_id"] in sample_ids], cfg["paths"]["corpus_sample"])
    log.info(f"sample corpus ({len(sample)} articles) written to {cfg['paths']['corpus_sample']}")
    log.count("sample articles", len(sample))

    report = cfg["paths"]["reports"] / "02-corpus-summary.md"
    report.write_text(summary_report(rows, excluded, log.counts), encoding="utf-8")
    log.info(f"summary written to {report}")
    log.close()
