"""Stages 5 and 7: check all stored answers again and report statistics.

`uv run ncse check analyst` and `uv run ncse check reviewer` (add `--sample`
for sample mode) make no LLM requests. For every stored record they:

1. run the checks of checks.py again on the accepted answer, with the prompt
   version recorded for it, and confirm that the stored result is exactly what
   the checks produce from the raw answer. Any difference means the record was
   changed after the fact (for example by hand) and is reported as an error;
2. confirm that failed articles really failed every attempt;
3. count statements, flags, failed checks, reviewer actions and tokens.

The report is written to reports/ (03-analyst-checks.md, 04-review-checks.md,
with `-sample` in the name in sample mode). The command exits with an error if
any record does not pass, so that it can be used before assembling the data.
"""

from collections import Counter

from . import checks
from .annotate import (corpus_folder, error_kind, load_articles, load_record, output_folder,
                       read_text, result_sha256)
from .prompts import load_prompt
from .quotes import Tolerance
from .runlog import RunLog


def recheck(record: dict, text: str, analyst_result: dict | None) -> list[str]:
    """Problems found when re-checking one record; empty if it is sound."""
    problems = []
    if record["status"] == "accepted":
        if record["step"] == "reviewer" and record.get("sent") is False:
            expected = checks.apply_review(analyst_result, [])
            if record["result"] != expected:
                problems.append("stored result differs from the unreviewed analyst result")
            return problems
        attempt = record["attempts"][record["accepted_attempt"] - 1]
        schema = load_prompt(record["step"], attempt["prompt_version"]).schema
        if record["step"] == "analyst":
            # the tolerance the answer was checked with is stored in the result (D-028)
            tolerance = Tolerance.from_config((record["result"] or {}).get("quote_tolerance"))
            result = checks.check_analyst(attempt["raw_response"], text, schema, tolerance)
        else:
            result = checks.check_review(attempt["raw_response"], analyst_result, schema)
        if not result.ok:
            problems.append("accepted answer fails the checks: " + "; ".join(result.errors[:3]))
        elif result_sha256(result.result) != result_sha256(record["result"]):
            problems.append("stored result is not what the checks produce from the raw answer")
    elif record["status"] == "failed":
        if any(a.get("accepted") for a in record["attempts"]):
            problems.append("marked failed although an attempt was accepted")
    return problems


def _pct(n: int, total: int) -> str:
    return f"{n} ({100 * n / total:.0f}%)" if total else str(n)


def _table(counter: Counter, head: tuple[str, str], total: int | None = None) -> list[str]:
    lines = [f"| {head[0]} | {head[1]} |", "|---|---|"]
    for key, n in sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        lines.append(f"| {key} | {_pct(n, total) if total else n} |")
    return lines if counter else ["(none)"]


def run(cfg: dict, step: str, sample: bool = False) -> None:
    log = RunLog(f"check-{step}{'-sample' if sample else ''}", cfg["paths"]["logs"])
    corpus = corpus_folder(cfg, sample)
    articles = load_articles(corpus)
    out = output_folder(cfg, step, sample)
    analyst_out = output_folder(cfg, "analyst", sample)

    status, failed_checks, flags, problems = Counter(), Counter(), Counter(), []
    tokens, attempts_hist, versions = Counter(), Counter(), Counter()
    by_periodical: Counter = Counter()
    fields = {name: Counter() for name in checks.CLAIM_FIELDS}
    st_level, actions, deleted_reasons = Counter(), Counter(), Counter()
    failed_articles = []
    item_failures, quote_match, failed_items = Counter(), Counter(), []
    n_statements = n_passages = n_deleted = 0

    for art in articles:
        aid = art["article_id"]
        record = load_record(out, aid)
        if record is None:
            status["not yet processed"] += 1
            continue
        status[record["status"]] += 1
        log.count(record["status"])
        analyst_result = None
        if step == "reviewer":
            analyst = load_record(analyst_out, aid)
            if analyst is None or analyst["status"] != "accepted":
                problems.append((aid, "review exists but there is no accepted analyst answer"))
                continue
            analyst_result = analyst["result"]
            if record.get("analyst_sha256") != result_sha256(analyst_result):
                problems.append((aid, "review belongs to an older analyst answer"))
                continue
        for p in recheck(record, read_text(corpus, art), analyst_result):
            problems.append((aid, p))
        for a in record["attempts"]:
            for e in a.get("errors", []):
                failed_checks[error_kind(e)] += 1
            for key in ("prompt_tokens", "completion_tokens"):
                tokens[key] += (a.get("usage") or {}).get(key, 0)
        tokens["requests"] += len(record["attempts"])
        if record["attempts"]:
            attempts_hist[len(record["attempts"])] += 1
        if record["status"] == "failed":
            failed_articles.append((aid, record["errors"]))
        if record["status"] != "accepted":
            continue
        versions[f"{record.get('model')} / prompt {record.get('prompt_version')}"] += 1
        for f in record["flags"]:
            flags[f["flag"]] += 1
        for item in record["result"].get("failed", []):
            item_failures[f"{item['item']}: {error_kind(item['errors'][0])}"] += 1
            failed_items.append((aid, item))
        for p in record["result"]["passages"]:
            n_passages += 1
            if "quote_match" in p:
                quote_match[p["quote_match"]] += 1
            for s in p["statements"]:
                n_statements += 1
                by_periodical[art["periodical"]] += 1
                st_level[s["evidence"]] += 1
                for name in checks.CLAIM_FIELDS:
                    claim = s[name]
                    if claim is None:
                        fields[name]["(empty)"] += 1
                        continue
                    key = claim["value"] if name not in checks.FREE_FIELDS else "(filled)"
                    fields[name][f"{key} · {claim['evidence']}"] += 1
                    if claim.get("review"):
                        actions[f"{name}: {claim['review']}"
                                + (f" {claim['evidence_analyst']}→{claim['evidence']}"
                                   if claim["review"] == "downgraded" else "")] += 1
                if s.get("deleted"):
                    n_deleted += 1
                    actions["whole statement: deleted"] += 1

    n_articles = sum(status.values())
    title = "Analyst answers (stage 5)" if step == "analyst" else "Reviewer answers (stage 7)"
    lines = [f"# Checks of the {step} answers{' — sample mode' if sample else ''}", "",
             f"Generated by `uv run ncse check {step}{' --sample' if sample else ''}`. "
             "No LLM requests were made: the stored answers were checked again (see `src/ncse/checkreport.py`).", "",
             f"## {title}", "",
             "| Articles | Number |", "|---|---|",
             *[f"| {k} | {v} |" for k, v in sorted(status.items())],
             f"| **total in corpus** | {n_articles} |", "",
             f"**Re-check:** {len(problems)} problem(s)." + ("" if not problems else " Listed below."), ""]
    if problems:
        lines += [f"- `{aid}`: {p}" for aid, p in problems] + [""]
    lines += ["## Requests and tokens", "",
              f"- requests (attempts): {tokens['requests']}",
              f"- prompt tokens: {tokens['prompt_tokens']:,}",
              f"- completion tokens: {tokens['completion_tokens']:,}", "",
              "Attempts per article:", "", *_table(attempts_hist, ("attempts", "articles")), "",
              "Model and prompt of the accepted answers:", "", *_table(versions, ("model / prompt", "articles")), "",
              "## Failed checks (all attempts)", "",
              "These checks concern an answer as a whole: a failed check makes the code reject the answer "
              "and ask again. For the analyst, they also include the failed items of rejected answers "
              "(set aside, not retried; D-027).", "",
              *_table(failed_checks, ("check", "times")), ""]
    if failed_articles:
        lines += ["## Failed articles", ""]
        lines += [f"- `{aid}`: {'; '.join(errs[:3])}" for aid, errs in failed_articles] + [""]
    if step == "analyst":
        lines += ["## Failed items in accepted answers", "",
                  "A passage whose quote does not match the article, or a statement that breaks a rule, is set "
                  "aside with its reasons; the rest of the answer is kept (D-027). A failed passage takes its "
                  "statements with it. Counted by the first reason.", "",
                  *_table(item_failures, ("item: reason", "times")), ""]
        if failed_items:
            lines += [f"- `{aid}` {item['where']}: {'; '.join(item['errors'])}" for aid, item in failed_items] + [""]
        lines += ["## How quotations matched the article", "",
                  "exact = only whitespace differs; normalised = same letters and digits (punctuation, "
                  "quotation marks, line breaks, hyphens, capitals ignored); approximate = a few characters "
                  "differ, flagged (D-028).", "",
                  *_table(quote_match, ("match", "passages"), n_passages), ""]
    lines += ["## Flags on accepted answers", "",
              "Flags do not reject an answer; they mark statements to look at.", "",
              *_table(flags, ("flag", "times")), ""]
    lines += ["## Statements", "",
              f"- passages: {n_passages}", f"- statements: {n_statements}", ""]
    if step == "analyst":
        lines += ["By periodical:", "", *_table(by_periodical, ("periodical", "statements")), ""]
    lines += ["Statement evidence level" + (" (after review)" if step == "reviewer" else "") + ":", "",
              *_table(st_level, ("level", "statements"), n_statements), ""]
    if step == "reviewer":
        lines += ["## Reviewer actions", "",
                  f"Statements deleted: {_pct(n_deleted, n_statements)}.", "",
                  *_table(actions, ("action", "times")), ""]
    lines += ["## Fields", "",
              "Values (for categories) or filled/empty (for names and titles), with evidence level.", ""]
    for name, counter in fields.items():
        lines += [f"### {name}", "", *_table(counter, ("value · evidence", "statements"), n_statements), ""]

    name = ("03-analyst-checks" if step == "analyst" else "04-review-checks") + ("-sample" if sample else "")
    report = cfg["paths"]["reports"] / f"{name}.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    log.info(f"report written to {report}")
    log.count("problems", len(problems))
    log.count("statements", n_statements)
    log.close()
    if problems:
        raise SystemExit(f"{len(problems)} record(s) did not pass the re-check; see {report}")
