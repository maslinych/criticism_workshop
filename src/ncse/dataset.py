"""Stage 8: assemble the dataset and its data dictionary.

`uv run ncse assemble` (add `--sample` for sample mode) reads the checked
records of the analyst and the reviewer (data/annotation/<mode>/) and the
corpus metadata, and writes plain CSV tables (UTF-8) to data/dataset/<mode>/:

- statements.csv   one row per evaluative statement, statements deleted by the
                   reviewer included and marked (README, "Expected outputs");
- articles.csv     one row per corpus article: whether it was annotated and
                   reviewed, how many statements it has;
- failed_items.csv passages and statements the checks set aside (D-027);
- runs.csv         the annotation runs with their models and settings;
- DATA_DICTIONARY.md   every column of the four tables in plain words;
- ASSEMBLY.json    where the data came from, when it was assembled, and a
                   checksum of each table.

Only code assembles: every value is taken from a stored record, never edited.
The quotation and the evaluative expression are always the exact text of the
article that the model's copy matched (D-028), never the model's copy.

`--annotation DIR` and `--out DIR` assemble an earlier run kept elsewhere,
for example a pilot moved aside by scripts/pilot.sh (D-035).
"""

import csv
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

from . import checks
from .annotate import corpus_folder, load_articles, load_record, result_sha256
from .config import PROJECT_ROOT
from .runlog import RunLog

FIELDS = checks.CLAIM_FIELDS

# ---------------------------------------------------------------- columns
# (name, description). This list is the single source of the data dictionary.

_FIELD_TEXT = {
    "creator": "the person whose work is judged (writer, composer, painter, dramatist, translator), "
               "as written in the source",
    "art": "the art the work belongs to: literature, music, theatre, visual art or other",
    "work_title": "the title of the judged work, as written in the source",
    "work_genre": "the kind of work (novel, opera, sermon, history, ...), as written where possible",
    "polarity": "positive or negative judgement",
    "sarcastic": "yes if the evaluation is ironic (says the opposite of what it means), otherwise no",
    "criterion": "the ground of the judgement: aesthetic value, moral value, usefulness, novelty or tradition",
    "quoted_source": "whose opinion the critic reports; empty means the critic's own voice",
}


def _field_columns(name: str) -> list[tuple[str, str]]:
    what = _FIELD_TEXT[name]
    return [
        (name, f"Value: {what}. Empty if the analyst left it empty. The value stays even if the reviewer "
               f"deleted it (see `{name}_review`)."),
        (f"{name}_evidence", "Evidence level after review: observed (the text says it), inferred (the text "
                             "implies it), suggested (the model's expectation). Empty if the field is empty."),
        (f"{name}_evidence_analyst", "Evidence level given by the analyst, before review."),
        (f"{name}_assumption", "The analyst's assumption behind an inferred or suggested value."),
        (f"{name}_review", "What the reviewer did to this field: deleted, downgraded, or empty (nothing)."),
        (f"{name}_review_reason", "The reviewer's reason for that action."),
    ]


STATEMENT_COLUMNS: list[tuple[str, str]] = [
    ("statement_id", "Unique identifier of the statement: passage identifier + `-s` + number (D-003)."),
    ("passage_id", "Identifier of the passage (quotation) the statement rests on: article identifier + `-p` "
                   "+ number. Statements sharing a passage come from the same quotation."),
    ("article_id", "Identifier of the article in the prepared corpus; the text is `texts/<article_id>.txt`."),
    ("periodical", "The Leader or The Monthly Repository."),
    ("issue_date", "Date of the issue (YYYY-MM-DD)."),
    ("year", "Year of the issue."),
    ("part", "For a long article annotated in parts (D-034): the part the passage came from; else empty."),
    ("quote", "The passage, exactly as it stands in the article's text file (OCR errors included)."),
    ("quote_start", "Position of the passage in the text file: characters from the start (counting from 0)."),
    ("quote_end", "Position just after the end of the passage."),
    ("quote_match", "How the model's copy of the passage matched the text: exact (only spacing differs), "
                    "normalised (same letters and digits) or approximate (a few characters differ; D-028)."),
    ("evaluative_expression", "The evaluative word or phrase, exactly as it stands in the text; it lies inside "
                              "`quote`."),
    ("expression_start", "Position of the evaluative expression in the text file."),
    ("expression_end", "Position just after the end of the evaluative expression."),
    ("expression_match", "How the model's copy of the expression matched (as `quote_match`)."),
    *[c for name in FIELDS for c in _field_columns(name)],
    ("evidence", "Evidence level of the statement after review: the lowest level among its fields that the "
                 "reviewer did not delete (D-004)."),
    ("evidence_analyst", "Evidence level of the statement as the analyst gave it."),
    ("deleted", "yes if the reviewer deleted the whole statement, otherwise no. Deleted statements stay in "
                "the table so that the review can be studied; filter on this column to use only kept ones."),
    ("deleted_reason", "The reviewer's reason for deleting the statement."),
    ("note", "The analyst's remark; required when `art` is other."),
    ("flags", "Warnings from the code checks on this statement or its passage, separated by `; ` (for "
              "example observed_not_found, approximate_quote, repeated_statement; docs/output-format.md, "
              "section 3). They do not reject anything; they mark rows to look at."),
    ("corpus_version", "Version of the prepared corpus the quotations refer to."),
    ("analyst_model", "Model name of the analyst, as requested from the service."),
    ("analyst_prompt_version", "Version of the analyst prompt (folder in prompts/analyst/)."),
    ("analyst_prompt_sha256", "First 12 characters of the checksum of the analyst instructions actually sent."),
    ("analyst_run_id", "The analyst run that produced the accepted answer (see runs.csv)."),
    ("analyst_answered_at", "Date and time of the accepted analyst answer."),
    ("reviewer_model", "Model name of the reviewer."),
    ("reviewer_prompt_version", "Version of the reviewer prompt (folder in prompts/reviewer/)."),
    ("reviewer_prompt_sha256", "First 12 characters of the checksum of the reviewer instructions actually sent."),
    ("reviewer_run_id", "The reviewer run that produced the accepted review (see runs.csv)."),
    ("reviewer_answered_at", "Date and time of the accepted review."),
]

ARTICLE_COLUMNS: list[tuple[str, str]] = [
    ("article_id", "Identifier of the article in the prepared corpus."),
    ("periodical", "The Leader or The Monthly Repository."),
    ("issue_date", "Date of the issue (YYYY-MM-DD)."),
    ("year", "Year of the issue."),
    ("heading", "Heading of the article, if any (from the corpus metadata)."),
    ("n_words", "Length of the article in words (from the corpus metadata)."),
    ("n_chars", "Length of the article in characters."),
    ("n_parts", "Number of parts the article was annotated in (1 = sent whole; D-034)."),
    ("analyst_status", "accepted, failed, or not processed."),
    ("reviewer_status", "accepted, failed, not processed, or outdated (the review belongs to an earlier "
                        "analyst answer and is not used)."),
    ("in_dataset", "yes if the article's statements are in statements.csv: both steps accepted. An article "
                   "with `in_dataset` yes and 0 statements was read and found to contain no evaluations."),
    ("n_passages", "Number of accepted passages."),
    ("n_statements", "Number of statements in statements.csv (deleted ones included)."),
    ("n_deleted", "Number of statements the reviewer deleted."),
    ("n_failed_items", "Number of passages and statements set aside by the checks (failed_items.csv)."),
    ("errors", "Why a step failed, if it did."),
]

FAILED_COLUMNS: list[tuple[str, str]] = [
    ("article_id", "Identifier of the article."),
    ("where", "Number of the passage or statement in the analyst's answer (p03, p03-s02)."),
    ("item", "passage (with all its statements) or statement."),
    ("n_statements", "For a failed passage: how many statements were set aside with it."),
    ("reasons", "Why the code set the item aside, separated by `; `."),
    ("answer", "What the model wrote for this item (JSON), kept so that the failure can be checked."),
]

RUN_COLUMNS: list[tuple[str, str]] = [
    ("run_id", "Identifier of the run (step + date and time it started)."),
    ("step", "analyst or reviewer."),
    ("model", "Model name requested from the service."),
    ("prompt_version", "Prompt version."),
    ("prompt_sha256", "First 12 characters of the checksum of the instructions."),
    ("settings", "Model settings sent with every request (JSON): temperature, length limit, and so on."),
    ("started", "When the run started."),
    ("finished", "When the run finished."),
    ("requests", "Number of requests sent in the run."),
    ("prompt_tokens", "Input tokens used."),
    ("completion_tokens", "Output tokens used (reasoning included)."),
    ("used_in_dataset", "yes if at least one accepted answer in the dataset comes from this run."),
]

TABLES = [("statements.csv", "One row per evaluative statement.", STATEMENT_COLUMNS),
          ("articles.csv", "One row per article of the corpus.", ARTICLE_COLUMNS),
          ("failed_items.csv", "Passages and statements of accepted analyst answers that the code set aside "
                               "(D-027). They are not statements of the dataset.", FAILED_COLUMNS),
          ("runs.csv", "One row per annotation run whose records were found.", RUN_COLUMNS)]


def data_dictionary() -> str:
    """The data dictionary, generated from the column lists above."""
    lines = ["# Data dictionary", "",
             "Generated by `uv run ncse assemble` from `src/ncse/dataset.py`; do not edit by hand. "
             "All tables are CSV files in UTF-8. An empty cell means no value.", "",
             "Terms: a *passage* is a verbatim quotation from an article; a *statement* is one evaluation "
             "in it: one target (creator or work) × one criterion × one polarity (D-003). *Analyst* and "
             "*reviewer* are the two LLM steps: the analyst proposes statements, the reviewer may only delete "
             "them or lower their evidence level (D-005). Allowed values and their meaning are defined in "
             "`docs/annotation-guidelines.md` and `docs/evidence-and-review.md`.", ""]
    for name, about, columns in TABLES:
        lines += [f"## {name}", "", about, "", "| Column | Meaning |", "|---|---|"]
        lines += [f"| `{c}` | {d} |" for c, d in columns]
        lines.append("")
    lines += ["## Controlled values", "",
              "| Column | Allowed values |", "|---|---|",
              *[f"| `{k}` | {', '.join(v)} |" for k, v in CONTROLLED.items()], ""]
    return "\n".join(lines)


LEVEL_VALUES = ["observed", "inferred", "suggested"]
CONTROLLED = {
    "art": ["literature", "music", "theatre", "visual art", "other"],
    "polarity": ["positive", "negative"],
    "sarcastic": ["yes", "no"],
    "criterion": ["aesthetic value", "moral value", "usefulness", "novelty", "tradition"],
    "evidence (and every `*_evidence` column)": LEVEL_VALUES,
    "`*_review`": ["deleted", "downgraded"],
    "deleted": ["yes", "no"],
    "quote_match, expression_match": ["exact", "normalised", "approximate"],
}


# ---------------------------------------------------------------- rows


def _accepted_attempts(record: dict) -> dict:
    """Accepted attempt of a record, per part (None for an article sent whole)."""
    if record.get("sent") is False:
        return {}
    if "parts" in record:
        return {a["part"]: a for a in record["attempts"] if a.get("accepted")}
    return {None: record["attempts"][record["accepted_attempt"] - 1]}


def _short(sha: str | None) -> str:
    return (sha or "")[:12]


def statement_rows(art: dict, analyst: dict, reviewer: dict, corpus_version: str) -> list[dict]:
    """The rows of statements.csv for one article whose both steps are accepted.

    The reviewer's result already holds the analyst's statements with the review
    applied (checks.apply_review), so the statements are read from it."""
    a_att, r_att = _accepted_attempts(analyst), _accepted_attempts(reviewer)
    flags: dict[str, list[str]] = {}
    for f in analyst.get("flags", []):
        flags.setdefault(f["where"], []).append(f["flag"])
    rows = []
    for p in reviewer["result"]["passages"]:
        pid = f"{art['article_id']}-{p['passage_id']}"
        part = p.get("part")
        aa, ra = a_att.get(part, {}), r_att.get(part, {})
        for s in p["statements"]:
            offset = p["quote_source"].find(s["evaluative_expression_source"])
            e_start = p["quote_start"] + offset
            row = {
                "statement_id": f"{art['article_id']}-{s['statement_id']}", "passage_id": pid,
                "article_id": art["article_id"], "periodical": art["periodical"],
                "issue_date": art["issue_date"], "year": art["issue_date"][:4], "part": part,
                "quote": p["quote_source"], "quote_start": p["quote_start"], "quote_end": p["quote_end"],
                "quote_match": p["quote_match"],
                "evaluative_expression": s["evaluative_expression_source"],
                "expression_start": e_start, "expression_end": e_start + len(s["evaluative_expression_source"]),
                "expression_match": s["expression_match"],
            }
            for name in FIELDS:
                c = s[name] or {}
                row.update({name: c.get("value"), f"{name}_evidence": c.get("evidence"),
                            f"{name}_evidence_analyst": c.get("evidence_analyst"),
                            f"{name}_assumption": c.get("assumption"), f"{name}_review": c.get("review"),
                            f"{name}_review_reason": c.get("review_reason")})
            row.update({
                "evidence": s["evidence"], "evidence_analyst": s["evidence_analyst"],
                "deleted": "yes" if s["deleted"] else "no", "deleted_reason": s["deleted_reason"],
                "note": s["note"],
                "flags": "; ".join(flags.get(p["passage_id"], []) + flags.get(s["statement_id"], [])),
                "corpus_version": corpus_version,
                "analyst_model": analyst.get("model"), "analyst_prompt_version": analyst.get("prompt_version"),
                "analyst_prompt_sha256": _short(analyst.get("prompt_sha256")),
                "analyst_run_id": aa.get("run_id"), "analyst_answered_at": aa.get("answered_at"),
                "reviewer_model": reviewer.get("model"), "reviewer_prompt_version": reviewer.get("prompt_version"),
                "reviewer_prompt_sha256": _short(reviewer.get("prompt_sha256")),
                "reviewer_run_id": ra.get("run_id"), "reviewer_answered_at": ra.get("answered_at"),
            })
            rows.append(row)
    return rows


def failed_rows(aid: str, analyst: dict) -> list[dict]:
    return [{"article_id": aid, "where": i["where"], "item": i["item"], "n_statements": i.get("statements"),
             "reasons": "; ".join(i["errors"]), "answer": json.dumps(i.get("answer"), ensure_ascii=False)}
            for i in (analyst.get("result") or {}).get("failed", [])]


def assemble(articles: list[dict], analyst_dir: Path, reviewer_dir: Path) -> dict:
    """Build all rows from the records (pure apart from reading the records)."""
    statements, article_rows, failed, run_ids = [], [], [], set()
    for art in articles:
        aid = art["article_id"]
        analyst, reviewer = load_record(analyst_dir, aid), load_record(reviewer_dir, aid)
        a_status = analyst["status"] if analyst else "not processed"
        r_status = reviewer["status"] if reviewer else "not processed"
        if (reviewer and analyst and a_status == "accepted"
                and reviewer.get("analyst_sha256") != result_sha256(analyst["result"])):
            r_status = "outdated"
        rows, errors = [], []
        for rec in (analyst, reviewer):
            if rec and rec["status"] == "failed":
                errors += [f"{rec['step']}: {e}" for e in rec["errors"]]
        if a_status == "accepted":
            failed += failed_rows(aid, analyst)
        in_dataset = a_status == "accepted" and r_status == "accepted"
        if in_dataset:
            rows = statement_rows(art, analyst, reviewer, analyst["corpus_version"])
            statements += rows
            for rec in (analyst, reviewer):
                run_ids |= {a.get("run_id") for a in _accepted_attempts(rec).values()}
        article_rows.append({
            "article_id": aid, "periodical": art["periodical"], "issue_date": art["issue_date"],
            "year": art["issue_date"][:4], "heading": art.get("heading", ""), "n_words": art["n_words"],
            "n_chars": art["n_chars"], "n_parts": len(analyst["parts"]) if analyst and "parts" in analyst else 1,
            "analyst_status": a_status, "reviewer_status": r_status, "in_dataset": "yes" if in_dataset else "no",
            "n_passages": len({r["passage_id"] for r in rows}), "n_statements": len(rows),
            "n_deleted": sum(r["deleted"] == "yes" for r in rows),
            "n_failed_items": len(failed_rows(aid, analyst)) if a_status == "accepted" else 0,
            "errors": "; ".join(errors)})
    return {"statements": statements, "articles": article_rows, "failed": failed, "run_ids": run_ids}


def run_rows(runs_dir: Path, used: set) -> list[dict]:
    rows = []
    for path in sorted(runs_dir.glob("*.json")) if runs_dir.exists() else []:
        r = json.loads(path.read_text(encoding="utf-8"))
        counts = r.get("counts", {})
        rows.append({"run_id": r["run_id"], "step": r["step"], "model": r.get("model"),
                     "prompt_version": r.get("prompt_version"), "prompt_sha256": _short(r.get("prompt_sha256")),
                     "settings": json.dumps(r.get("settings"), ensure_ascii=False, sort_keys=True),
                     "started": r.get("started"), "finished": r.get("finished"),
                     "requests": counts.get("requests", 0), "prompt_tokens": counts.get("prompt tokens", 0),
                     "completion_tokens": counts.get("completion tokens", 0),
                     "used_in_dataset": "yes" if r["run_id"] in used else "no"})
    return rows


# ---------------------------------------------------------------- writing


def _cell(v) -> str:
    return "" if v is None else str(v)


def write_csv(path: Path, columns: list[tuple[str, str]], rows: list[dict]) -> str:
    names = [c for c, _ in columns]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(names)
        for row in rows:
            w.writerow([_cell(row.get(n)) for n in names])
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, capture_output=True, text=True)
        return out.stdout.strip() or None
    except OSError:
        return None


def default_folders(cfg: dict, sample: bool) -> tuple[Path, Path]:
    mode = "sample" if sample else "full"
    return cfg["paths"]["annotation"] / mode, cfg["paths"]["dataset"] / mode


def run(cfg: dict, sample: bool = False, annotation: Path | None = None, out: Path | None = None) -> Path:
    default_ann, default_out = default_folders(cfg, sample)
    annotation, out = Path(annotation or default_ann), Path(out or default_out)
    name = "assemble" + ("-sample" if sample else "")
    log = RunLog(name, cfg["paths"]["logs"])
    if not (annotation / "analyst").exists():
        raise SystemExit(f"no analyst records in {annotation}: run `uv run ncse analyse` first")
    articles = load_articles(corpus_folder(cfg, sample))
    log.info(f"records from {annotation}, {len(articles)} articles in the corpus, output {out}")
    data = assemble(articles, annotation / "analyst", annotation / "reviewer")
    runs = run_rows(annotation / "runs", data["run_ids"])
    out.mkdir(parents=True, exist_ok=True)
    sums = {}
    for (fname, _, columns), rows in zip(TABLES, (data["statements"], data["articles"], data["failed"], runs)):
        sums[fname] = write_csv(out / fname, columns, rows)
    (out / "DATA_DICTIONARY.md").write_text(data_dictionary(), encoding="utf-8")
    status = {}
    for r in data["articles"]:
        key = f"analyst {r['analyst_status']}, reviewer {r['reviewer_status']}"
        status[key] = status.get(key, 0) + 1
    info = {"assembled_at": dt.datetime.now().isoformat(timespec="seconds"), "code_commit": _git_commit(),
            "annotation_folder": str(annotation.resolve().relative_to(PROJECT_ROOT)
                                     if annotation.resolve().is_relative_to(PROJECT_ROOT) else annotation),
            "corpus": "corpus_sample" if sample else "full",
            "articles": len(data["articles"]), "articles_in_dataset": sum(r["in_dataset"] == "yes"
                                                                          for r in data["articles"]),
            "article_status": status, "statements": len(data["statements"]),
            "statements_deleted": sum(r["deleted"] == "yes" for r in data["statements"]),
            "failed_items": len(data["failed"]), "sha256": sums}
    (out / "ASSEMBLY.json").write_text(json.dumps(info, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for k, v in status.items():
        log.info(f"articles: {k}: {v}")
        if "outdated" in k or "failed" in k:
            log.count("articles left out (failed or outdated review)", v)
    log.count("articles in dataset", info["articles_in_dataset"])
    log.count("statements", info["statements"])
    log.count("statements deleted by reviewer", info["statements_deleted"])
    log.count("failed items", info["failed_items"])
    log.info(f"dataset written to {out}")
    log.close()
    return out
