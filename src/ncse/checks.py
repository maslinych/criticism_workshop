"""Checking the answers of the two LLM steps (stages 5 and 7; D-022, D-024).

Every answer is checked by code before it is accepted. The checks implement
docs/output-format.md, sections 3 and 5.2:

- the answer must be a bare JSON object, as the prompts instruct (no text or
  Markdown fences around it, no repeated keys);
- it must match the JSON schema of its prompt version;
- the analyst's quotations must match passages of the article, and each
  evaluative expression must lie inside its quotation (quotes.py: exact,
  normalised or, with a flag, approximate; D-028);
- the evidence rules must hold (assumptions for inferred and suggested claims);
- the reviewer may only delete or downgrade, within the limits of D-024.

A check produces one of three outcomes (D-027):
- an *error*: the answer as a whole is unusable (not a bare JSON object, wrong
  format; for the reviewer, any action outside its limits). The answer is
  rejected and the request is retried;
- a *failed item* (analyst only): one passage or statement breaks a rule. It is
  set aside, with its reasons, in the result's `failed` list; the rest of the
  answer is accepted;
- a *flag*: the item is accepted, and the flag is kept with the data for
  inspection.

All functions here are pure: they take text and return results, and never call
the LLM or touch files, so that they can be tested directly.
"""

import copy
import json
from dataclasses import dataclass, field

import jsonschema

from .quotes import Match, Tolerance, contains_loose, match, squeeze

CLAIM_FIELDS = ["creator", "art", "work_title", "work_genre", "polarity",
                "sarcastic", "criterion", "quoted_source"]
FREE_FIELDS = ["creator", "work_title", "work_genre", "quoted_source"]
LEVELS = {"observed": 3, "inferred": 2, "suggested": 1}
# What the reviewer may delete on its own (D-024). Everything in CLAIM_FIELDS may be downgraded.
DELETABLE = {"statement", "creator", "work_title", "work_genre"}
# Pairs of marks that must not wrap a whole name or title (the prompt asks to leave them out).
WRAPPERS = [("_", "_"), ('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’")]
MAX_SCHEMA_ERRORS = 15


@dataclass
class CheckResult:
    """Outcome of checking one answer."""

    errors: list[str] = field(default_factory=list)
    flags: list[dict] = field(default_factory=list)
    answer: dict | None = None  # the parsed answer, if it could be parsed
    result: dict | None = None  # the processed result, if there are no errors

    @property
    def ok(self) -> bool:
        return not self.errors


# ---------------------------------------------------------------- parsing


def _no_duplicate_keys(pairs):
    keys = [k for k, _ in pairs]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    if dupes:
        raise ValueError(f"key(s) given twice in one object: {', '.join(dupes)}")
    return dict(pairs)


def parse_answer(raw: str | None, check: CheckResult) -> dict | None:
    """Parse a bare JSON object. Anything around it breaks the instructions."""
    if raw is None or not raw.strip():
        check.errors.append("the answer is empty")
        return None
    text = raw.strip()
    if text.startswith("```"):
        check.errors.append("the answer is wrapped in Markdown code fences (```); give the JSON object only")
        return None
    if not (text.startswith("{") and text.endswith("}")):
        check.errors.append("the answer must be a single JSON object and nothing else: "
                            "it must start with '{' and end with '}', with no text before or after it")
        return None
    try:
        obj = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except ValueError as e:  # json.JSONDecodeError is a ValueError
        check.errors.append(f"the answer is not valid JSON: {e}")
        return None
    return obj


def schema_errors(obj, schema: dict) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    found = sorted(validator.iter_errors(obj), key=lambda e: list(e.absolute_path))
    out = []
    for e in found[:MAX_SCHEMA_ERRORS]:
        where = "/".join(str(p) for p in e.absolute_path) or "(top level)"
        out.append(f"format error at {where}: {e.message}")
    if len(found) > MAX_SCHEMA_ERRORS:
        out.append(f"... and {len(found) - MAX_SCHEMA_ERRORS} more format errors")
    return out


def _short(text: str, n: int = 70) -> str:
    text = squeeze(text)
    return text if len(text) <= n else text[: n - 1] + "…"


def _blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def statement_level(statement: dict, skip_deleted: bool = False) -> str:
    """The lowest evidence level among a statement's claims (D-004).
    The quote is observed by definition, so the default is 'observed'."""
    level = "observed"
    for name in CLAIM_FIELDS:
        claim = statement.get(name)
        if claim is None or (skip_deleted and claim.get("review") == "deleted"):
            continue
        if LEVELS[claim["evidence"]] < LEVELS[level]:
            level = claim["evidence"]
    return level


# ---------------------------------------------------------------- analyst


def check_analyst(raw: str | None, text: str, schema: dict,
                  tolerance: Tolerance = Tolerance(), span: tuple[int, int] | None = None) -> CheckResult:
    """Check one analyst answer for one article (stage 5).

    `text` is the article's text file, unchanged. Problems with the answer as a
    whole (not a bare JSON object, wrong format) are *errors*: the answer is
    rejected. Problems with one passage or statement do not reject the answer
    (D-027): the item is set aside in `result["failed"]` with its reasons, and
    the rest is accepted. A passage whose quote is not found fails with all its
    statements.

    `result["passages"]` holds the accepted passages with short identifiers
    (p01, p01-s01) numbered over the whole answer, so that failed items keep
    their place; the position and exact source text of each quote and
    evaluative expression; how they matched (D-028); and the statement levels.

    For one part of a long article (D-034), `span` gives the part's (start,
    end) in `text`: quotes must lie in the part, and their positions are
    counted within the part (parts.join_analyst shifts them). Values marked
    observed are still looked for in the whole article."""
    check = CheckResult()
    obj = parse_answer(raw, check)
    if obj is None:
        return check
    check.answer = obj
    check.errors += schema_errors(obj, schema)
    if check.errors:
        return check

    part = text if span is None else text[span[0]:span[1]]
    where_found = "the article" if span is None else "this part of the article"
    passages, failed = [], []
    seen_quotes: dict[str, str] = {}
    seen_statements: dict[str, str] = {}
    previous_start = -1
    for pi, passage in enumerate(obj["passages"], start=1):
        pid = f"p{pi:02d}"
        quote = passage["quote"]
        found = match(part, quote, tolerance)
        if found is None:
            failed.append({"where": pid, "item": "passage", "statements": len(passage["statements"]),
                           "errors": [f"passage {pid}: the quote does not match any passage of {where_found}, "
                                      "even allowing for punctuation, capitals, line breaks and a few "
                                      f"changed characters: \"{_short(quote)}\""],
                           "answer": passage})
            continue
        source = part[found.start:found.end]
        if found.count > 1:
            check.flags.append({"where": pid, "flag": "ambiguous_quote",
                                "detail": f"the quote occurs {found.count} times; the first is recorded"})
        if found.level == "approximate":
            check.flags.append({"where": pid, "flag": "approximate_quote",
                                "detail": f"{found.char_errors} character(s) differ from the article: "
                                          f"\"{_short(source)}\""})
        if found.start < previous_start:
            check.flags.append({"where": pid, "flag": "passage_order",
                                "detail": "passage comes before the previous one in the article"})
        previous_start = found.start
        key = squeeze(source)
        if key in seen_quotes:
            check.flags.append({"where": pid, "flag": "repeated_quote",
                                "detail": f"same quote as {seen_quotes[key]}"})
        seen_quotes.setdefault(key, pid)

        statements = []
        for si, st in enumerate(passage["statements"], start=1):
            sid = f"{pid}-s{si:02d}"
            st_key = json.dumps(st, sort_keys=True)
            if st_key in seen_statements:
                check.flags.append({"where": sid, "flag": "repeated_statement",
                                    "detail": f"identical to {seen_statements[st_key]}"})
            seen_statements.setdefault(st_key, sid)
            errors, expr = _check_statement(st, sid, source, text, tolerance, check)
            if errors:
                failed.append({"where": sid, "item": "statement", "errors": errors, "answer": st})
                continue
            statements.append({"statement_id": sid, **st,
                               "evaluative_expression_source": source[expr.start:expr.end],
                               "expression_match": expr.level, "evidence": statement_level(st)})
        passages.append({"passage_id": pid, "quote": quote, "quote_source": source,
                         "quote_start": found.start, "quote_end": found.end,
                         "quote_match": found.level, "quote_char_errors": found.char_errors,
                         "statements": statements})

    check.result = {"passages": passages, "failed": failed, "quote_tolerance": tolerance.as_dict()}
    return check


def _check_statement(st: dict, sid: str, source: str, text: str, tolerance: Tolerance,
                     check: CheckResult) -> tuple[list[str], Match | None]:
    """The reasons why one statement fails (empty if it passes), and where its
    evaluative expression lies in the quote's source text."""
    errors = []
    expr = st["evaluative_expression"]
    found = match(source, expr, tolerance)
    if found is None:
        errors.append(f"statement {sid}: the evaluative expression \"{_short(expr, 50)}\" "
                      "does not occur inside its quote")
    elif found.level == "approximate":
        check.flags.append({"where": sid, "flag": "approximate_expression",
                            "detail": f"{found.char_errors} character(s) differ from the article: "
                                      f"\"{_short(source[found.start:found.end], 50)}\""})
    if all(st[name] is None for name in ("creator", "work_title", "work_genre")):
        errors.append(f"statement {sid}: no target: at least one of creator, work_title "
                      "and work_genre must be filled")
    if st["art"]["value"] == "other" and _blank(st["note"]):
        errors.append(f"statement {sid}: art is 'other', so note must explain why")
    if isinstance(st["note"], str) and not st["note"].strip():
        errors.append(f"statement {sid}: note must be null or a non-empty text")
    for name in CLAIM_FIELDS:
        claim = st[name]
        if claim is None:
            continue
        level, assumption = claim["evidence"], claim["assumption"]
        if level == "observed" and assumption is not None:
            errors.append(f"statement {sid}, {name}: an observed claim must have assumption null")
        if level != "observed" and _blank(assumption):
            errors.append(f"statement {sid}, {name}: an {level} claim needs an assumption")
        if name in FREE_FIELDS:
            value = claim["value"]
            if value != value.strip():
                errors.append(f"statement {sid}, {name}: the value has spaces at its start or end")
            elif any(value.startswith(a) and value.endswith(b) and len(value) > 1 for a, b in WRAPPERS):
                errors.append(f"statement {sid}, {name}: write \"{_short(value, 40)}\" without "
                              "the surrounding quotation marks or underscores")
            if level == "observed" and not contains_loose(text, value):
                check.flags.append({"where": sid, "flag": "observed_not_found",
                                    "detail": f"{name} \"{_short(value, 40)}\" is marked observed "
                                              "but does not occur in the article"})
    return errors, found


def reviewer_input(analyst_result: dict) -> str:
    """The analyst's statements as shown to the reviewer: the analyst's own
    fields plus short identifiers, nothing else (evidence-and-review.md, 5)."""
    shown = {"passages": [
        {"passage_id": p["passage_id"], "quote": p["quote_source"],
         "statements": [
             {"statement_id": s["statement_id"],
              "evaluative_expression": s["evaluative_expression"],
              **{name: s[name] for name in CLAIM_FIELDS},
              "note": s["note"]}
             for s in p["statements"]]}
        for p in analyst_result["passages"]]}
    return json.dumps(shown, ensure_ascii=False, indent=1)


def statement_count(analyst_result: dict) -> int:
    return sum(len(p["statements"]) for p in analyst_result["passages"])


# ---------------------------------------------------------------- reviewer


def check_review(raw: str | None, analyst_result: dict, schema: dict) -> CheckResult:
    """Check one reviewer answer against the analyst's accepted result (stage 7).
    On success, `result` is the analyst's result with the actions applied:
    deleted items are kept and marked, downgraded levels are lowered."""
    check = CheckResult()
    obj = parse_answer(raw, check)
    if obj is None:
        return check
    check.answer = obj
    check.errors += schema_errors(obj, schema)
    if check.errors:
        return check

    statements = {s["statement_id"]: s for p in analyst_result["passages"] for s in p["statements"]}
    done: set[tuple[str, str]] = set()
    deleted: set[str] = set()
    touched: set[str] = set()
    for i, act in enumerate(obj["actions"], start=1):
        sid, name, kind, new = act["statement_id"], act["field"], act["action"], act["new_evidence"]
        where = f"action {i} ({sid}, {name})"
        if sid not in statements:
            check.errors.append(f"{where}: there is no statement {sid}")
            continue
        if not act["reason"].strip():
            check.errors.append(f"{where}: the reason is empty")
        if (sid, name) in done:
            check.errors.append(f"{where}: a second action on the same field")
        done.add((sid, name))
        if name == "statement":
            if sid in touched:
                check.errors.append(f"{where}: the statement is deleted, so give no other action for it")
            deleted.add(sid)
        elif sid in deleted:
            check.errors.append(f"{where}: the statement is deleted, so give no other action for it")
        touched.add(sid)

        claim = None if name == "statement" else statements[sid].get(name)
        if name != "statement" and claim is None:
            check.errors.append(f"{where}: the field is empty, so there is nothing to delete or downgrade")
            continue
        if kind == "delete":
            if new is not None:
                check.errors.append(f"{where}: a deletion must have new_evidence null")
            if name not in DELETABLE:
                check.errors.append(f"{where}: {name} cannot be deleted on its own; "
                                    "delete the whole statement instead")
        else:  # downgrade
            if name == "statement":
                check.errors.append(f"{where}: a whole statement cannot be downgraded; downgrade its fields")
            elif new is None:
                check.errors.append(f"{where}: a downgrade needs new_evidence")
            elif LEVELS[new] >= LEVELS[claim["evidence"]]:
                check.errors.append(f"{where}: {claim['evidence']} → {new} does not lower the level")

    if not check.errors:
        check.result = apply_review(analyst_result, obj["actions"])
    return check


def apply_review(analyst_result: dict, actions: list[dict]) -> dict:
    """Apply checked reviewer actions. Nothing is removed: deletions are marks."""
    result = copy.deepcopy(analyst_result)
    by_id = {s["statement_id"]: s for p in result["passages"] for s in p["statements"]}
    for st in by_id.values():
        st["evidence_analyst"] = st["evidence"]
        st["deleted"] = False
        st["deleted_reason"] = None
        for name in CLAIM_FIELDS:
            if st[name] is not None:
                st[name] = {**st[name], "evidence_analyst": st[name]["evidence"],
                            "review": None, "review_reason": None}
    for act in actions:
        st = by_id[act["statement_id"]]
        if act["field"] == "statement":
            st["deleted"], st["deleted_reason"] = True, act["reason"]
            continue
        claim = st[act["field"]]
        if act["action"] == "delete":
            claim["review"], claim["review_reason"] = "deleted", act["reason"]
        else:
            claim["evidence"] = act["new_evidence"]
            claim["review"], claim["review_reason"] = "downgraded", act["reason"]
    for st in by_id.values():
        st["evidence"] = statement_level(st, skip_deleted=True)
    return result


# ---------------------------------------------------------------- feedback


def retry_message(errors: list[str], cut_off: bool = False) -> str:
    """What the model is told after a rejected answer (D-022).

    After an answer cut off at the length limit, the model is also told that
    only its beginning was shown and asked not to repeat itself (D-026).
    """
    lines = "\n".join(f"- {e}" for e in errors)
    extra = ("Only the beginning of your answer is shown above. Do not write any text outside the JSON "
             "object and do not repeat yourself.\n" if cut_off else "")
    return ("Your answer was rejected by the automatic checks for these reasons:\n"
            f"{lines}\n\n{extra}"
            "Answer again with the complete, corrected JSON object only, following all the instructions.")
