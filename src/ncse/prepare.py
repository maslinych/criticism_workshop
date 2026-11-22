"""Stage 3: write the prepared corpus.

Output (for the full corpus in data/corpus/full/, and for the small sample in corpus_sample/):
  texts/<article_id>.txt   the article text: box texts joined by a blank line, OCR unchanged
  metadata.csv             one row per article (columns described in METADATA_COLUMNS)
and a summary report in reports/02-corpus-summary.md.

Running the stage again rebuilds the corpus from scratch; the result is identical
as long as the source data and config.yaml are unchanged.
"""

import csv
import re
import random
import shutil
from collections import Counter
from pathlib import Path

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
    "heading": "text of the title box(es) heading the article, separated by ' | '; empty if none",
    "n_words": "number of words in the text file (split at whitespace)",
    "n_chars": "number of characters in the text file",
    "n_entries": "number of NCSE boxes the article was built from",
    "selected_share": "share of the article's characters in boxes that meet the selection rule",
    "ncse_text_types": "NCSE text type label of each box, in order, separated by ';'",
    "ncse_topics": "NCSE topic labels of each box, in order, separated by ';' (several topics per box joined by '|')",
    "ncse_entry_ids": "NCSE box identifiers (bbox_uid) the article was built from, in reading order, separated by ';'",
    "rebuild_notes": "notes on how the article was rebuilt, separated by ' / '",
}


def article_rows(cfg: dict, periodical: dict, log: RunLog) -> list[tuple[dict, str]]:
    boxes = load_boxes(cfg, periodical)
    log.info(f"{periodical['name']}: {boxes.height:,} boxes in {boxes['issue_id'].n_unique()} issues")
    log.count("boxes read", boxes.height)
    log.count("boxes meeting selection rule", int(boxes["selected"].sum()))
    rb = cfg["rebuild"]
    rows = []
    for (issue_id,), issue in boxes.group_by(["issue_id"], maintain_order=True):
        articles = rebuild_issue(issue.to_dicts(), rb["max_gap"], set(rb["exclude_classes"]))
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
                "ncse_text_types": ";".join(b["text_type"] for b in art.boxes),
                "ncse_topics": ";".join("|".join(b["topics"]) for b in art.boxes),
                "ncse_entry_ids": ";".join(b["bbox_uid"] for b in art.boxes),
                "rebuild_notes": " / ".join(art.notes),
                "_text_boxes": len(art.boxes) - art.heading_count,  # for the summary only, not written
            }
            rows.append((row, text))
            for note in art.notes:
                # count the kind of note, without the numbers and box identifiers
                log.count("note: " + re.sub(r"\d+ ", "", note.split(":")[0]))
    log.info(f"  {len(rows):,} articles built")
    log.count("articles built", len(rows))
    return rows


def write_corpus(rows: list[tuple[dict, str]], folder: Path) -> None:
    """Write texts/ and metadata.csv into folder, replacing old versions safely."""
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / "texts.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    for row, text in rows:
        (tmp / row["file_name"]).write_text(text, encoding="utf-8", newline="")
    with open(folder / "metadata.csv.tmp", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(METADATA_COLUMNS), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(row for row, _ in rows)
    shutil.rmtree(folder / "texts", ignore_errors=True)
    tmp.rename(folder / "texts")
    (folder / "metadata.csv.tmp").replace(folder / "metadata.csv")


def choose_sample(rows: list[tuple[dict, str]], cfg: dict) -> list[tuple[dict, str]]:
    s = cfg["sample"]
    rng = random.Random(s["seed"])
    chosen = []
    for periodical in cfg["periodicals"]:
        pool = [r for r in rows if r[0]["periodical"] == periodical["name"] and r[0]["n_chars"] >= s["min_chars"]]
        chosen += rng.sample(pool, min(s["articles_per_periodical"], len(pool)))
    return sorted(chosen, key=lambda r: r[0]["article_id"])


def summary_report(rows: list[tuple[dict, str]], counts: Counter) -> str:
    lines = [
        "# Prepared corpus: summary",
        "",
        "Generated by `uv run ncse prepare`. Do not edit by hand.",
        "",
        "## Articles per periodical",
        "",
        "| Periodical | Articles | Words | Median words | With heading | Crossing a page break | Only one text box |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    by_per: dict[str, list[dict]] = {}
    for row, _ in rows:
        by_per.setdefault(row["periodical"], []).append(row)
    for per, rs in by_per.items():
        words = sorted(r["n_words"] for r in rs)
        lines.append(
            f"| {per} | {len(rs):,} | {sum(words):,} | {words[len(words) // 2]:,} "
            f"| {sum(bool(r['heading']) for r in rs):,} | {sum('crosses page break' in r['rebuild_notes'] for r in rs):,} "
            f"| {sum(r['_text_boxes'] == 1 for r in rs):,} |"
        )
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
    rows = []
    for periodical in cfg["periodicals"]:
        rows += article_rows(cfg, periodical, log)

    write_corpus(rows, cfg["paths"]["corpus"])
    log.info(f"full corpus written to {cfg['paths']['corpus']}")
    sample = choose_sample(rows, cfg)
    write_corpus(sample, cfg["paths"]["corpus_sample"])
    log.info(f"sample corpus ({len(sample)} articles) written to {cfg['paths']['corpus_sample']}")
    log.count("sample articles", len(sample))

    report = cfg["paths"]["reports"] / "02-corpus-summary.md"
    report.write_text(summary_report(rows, log.counts), encoding="utf-8")
    log.info(f"summary written to {report}")
    log.close()
