"""Tests for the quotation matcher and the checks of both LLM steps (stages 5 and 7)."""

import copy
import json

import pytest

from ncse import checks
from ncse.prompts import load_prompt
from ncse.quotes import Tolerance, contains, contains_loose, find_all, match, normalize

ANALYST_SCHEMA = load_prompt("analyst", "v1").schema
REVIEWER_SCHEMA = load_prompt("reviewer", "v1").schema

TEXT = ("THE DELUGE.\n\nMr. Hartley's new oratorio, _The Deluge_, is a laborious and\n"
        "tedious performance; we are told by a contemporary that it is 'the finest sacred work "
        "of the age,' a judgement in which we cannot concur. The patriicians applauded.")
QUOTE = ("Mr. Hartley's new oratorio, _The Deluge_, is a laborious and tedious performance; "
         "we are told by a contemporary that it is 'the finest sacred work of the age,' a "
         "judgement in which we cannot concur.")


def claim(value, evidence="observed", assumption=None):
    return {"value": value, "evidence": evidence, "assumption": assumption}


def statement(**changes):
    st = {"evaluative_expression": "laborious and tedious",
          "creator": claim("Mr. Hartley"), "art": claim("music"), "work_title": claim("The Deluge"),
          "work_genre": claim("oratorio"), "polarity": claim("negative"), "sarcastic": claim("no"),
          "criterion": claim("aesthetic value"), "quoted_source": None, "note": None}
    st.update(changes)
    return st


def answer(*statements, quote=QUOTE):
    return {"passages": [{"quote": quote, "statements": list(statements) or [statement()]}]}


def analyse(obj, text=TEXT, tolerance=Tolerance()):
    raw = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return checks.check_analyst(raw, text, ANALYST_SCHEMA, tolerance)


def item_errors(check):
    """The reasons of all items set aside in an accepted answer (D-027)."""
    assert check.ok, check.errors  # an item failure never rejects the whole answer
    return [e for item in check.result["failed"] for e in item["errors"]]


# ------------------------------------------------------------ quotation matching


def test_exact_matching_tolerates_only_whitespace():
    assert find_all(TEXT, QUOTE)  # line break in the text, space in the quote
    assert find_all(TEXT, "  laborious   and\ttedious ")
    assert not find_all(TEXT, "laborious and tedious performance,")  # punctuation differs
    assert not find_all(TEXT, "The patricians applauded.")  # OCR error "corrected"
    assert not find_all(TEXT, "the finest sacred work of the age,\" a judgement")  # quote mark changed
    assert not find_all(TEXT, "mr. hartley's")  # capitals differ


def test_quote_positions_point_into_the_original_text():
    (start, end), = find_all(TEXT, "laborious and tedious")
    assert TEXT[start:end] == "laborious and\ntedious"


def test_normalised_match_ignores_punctuation_capitals_and_line_breaks():
    for quote in ["laborious and tedious performance,",           # punctuation differs
                  "the finest sacred work of the age,\" a judgement",  # quotation mark changed
                  "mr. hartley's",                                 # capitals differ
                  "MR HARTLEY’S NEW ORATORIO"]:                    # all of it
        m = match(TEXT, quote)
        assert m and m.level == "normalised" and m.char_errors == 0, quote
    text = "known and appre-\n\nelated all over Europe.\n\nand so on"
    m = match(text, "known and appre-elated all over Europe and so")  # broken word, stray full stop
    assert m and m.level == "normalised"
    assert text[m.start:m.end] == "known and appre-\n\nelated all over Europe.\n\nand so"


def test_source_span_keeps_punctuation_the_quote_has():
    m = match(TEXT, "a laborious and tedious performance;")
    assert m.level == "exact"
    m = match(TEXT, "A laborious and tedious performance;")
    assert m.level == "normalised" and TEXT[m.start:m.end] == "a laborious and\ntedious performance;"
    m = match(TEXT, "the finest sacred work of the age,\"")
    assert TEXT[m.start:m.end] == "the finest sacred work of the age,'"


def test_approximate_match_allows_a_few_changed_characters():
    m = match(TEXT, "The patricians applauded.")  # OCR error "corrected": one letter less
    assert m and m.level == "approximate" and m.char_errors == 1
    assert TEXT[m.start:m.end] == "The patriicians applauded."
    m = match(TEXT, QUOTE.replace("laborious", "labourious").replace("concur", "concurr"))
    assert m and m.level == "approximate" and m.char_errors == 2
    # different words are not "a few characters"
    assert match(TEXT, "The plebeians applauded.") is None
    assert match(TEXT, QUOTE.replace("laborious and tedious", "brilliant and moving")) is None


def test_approximate_limit_depends_on_length():
    tol = Tolerance(max_char_errors=3, max_error_share=0.05)
    assert [tol.allowed(n) for n in (10, 19, 20, 40, 60, 500)] == [0, 0, 1, 2, 3, 3]
    assert match(TEXT, "laborous and tedious") is None  # 18 letters: no error allowed
    assert match(TEXT, "The patricians applauded.", Tolerance(max_char_errors=0)) is None


def test_loose_matches_must_start_and_end_at_word_boundaries():
    text = "Nor was there any ground for supposing that."
    assert match(text, "no ground for supposing") is None  # would be "ny ground" with one change
    assert match(text, "NY ground for supposing") is None  # normalised level, starts mid-word
    assert match(text, "Any ground for supposing").level == "normalised"


def test_contains_loose():
    assert contains_loose(TEXT, "Mr Hartley")
    assert not contains_loose(TEXT, "John Hartley")


def test_normalize_maps_characters_back():
    norm, where = normalize("  a \n\n b ")
    assert norm == "a b"
    assert [where[0], where[2]] == [2, 7]


def test_contains_can_ignore_case():
    assert contains(TEXT, "THE DELUGE", ignore_case=True)
    assert not contains(TEXT, "THE DELUGE ARRIVES", ignore_case=True)


# ------------------------------------------------------------ analyst: accepted answers


def test_valid_answer_is_accepted_with_identifiers_and_positions():
    check = analyse(answer(statement(), statement(
        evaluative_expression="cannot concur",
        criterion=claim("aesthetic value", "inferred", "The rejection concerns artistic rank."))))
    assert check.ok, check.errors
    p = check.result["passages"][0]
    assert p["passage_id"] == "p01"
    assert TEXT[p["quote_start"]:p["quote_end"]].replace("\n", " ") == QUOTE
    assert [s["statement_id"] for s in p["statements"]] == ["p01-s01", "p01-s02"]
    assert [s["evidence"] for s in p["statements"]] == ["observed", "inferred"]
    assert p["quote_match"] == "exact" and p["quote_source"] == TEXT[p["quote_start"]:p["quote_end"]]
    assert p["statements"][0]["evaluative_expression_source"] == "laborious and\ntedious"
    assert check.result["failed"] == []
    assert check.result["quote_tolerance"] == {"max_char_errors": 3, "max_error_share": 0.05}


def test_tidied_quote_is_accepted_with_its_source_text():
    check = analyse(answer(statement(evaluative_expression="Laborious and Tedious"),
                           quote=QUOTE.replace("'", "\u2019").upper()))
    p = check.result["passages"][0]
    assert p["quote_match"] == "normalised" and not check.flags
    assert p["quote_source"].replace("\n", " ") == QUOTE
    assert p["statements"][0]["expression_match"] == "normalised"


def test_approximate_quote_is_accepted_with_a_flag():
    check = analyse(answer(quote=QUOTE.replace("laborious", "labourious")))
    assert check.ok and check.result["passages"][0]["quote_match"] == "approximate"
    assert [f["flag"] for f in check.flags] == ["approximate_quote"]


def test_empty_answer_list_is_valid():
    check = analyse({"passages": []})
    assert check.ok and check.result["passages"] == [] and check.result["failed"] == []


# ------------------------------------------------------------ analyst: instruction adherence


@pytest.mark.parametrize("raw, expected", [
    ("", "empty"),
    ("```json\n{\"passages\": []}\n```", "code fences"),
    ("Here is the JSON: {\"passages\": []}", "single JSON object"),
    ("{\"passages\": [}", "not valid JSON"),
    ("{\"passages\": [], \"passages\": []}", "given twice"),
])
def test_answers_that_are_not_bare_json_are_rejected(raw, expected):
    check = analyse(raw)
    assert not check.ok and expected in check.errors[0]


def test_schema_violations_are_rejected():
    bad = answer(statement(polarity=claim("mixed")))
    assert any("format error" in e for e in analyse(bad).errors)
    missing = answer(statement())
    del missing["passages"][0]["statements"][0]["note"]
    assert any("note" in e for e in analyse(missing).errors)
    extra = answer(statement(strength=claim("weak")))
    assert any("format error" in e for e in analyse(extra).errors)
    no_statements = {"passages": [{"quote": QUOTE, "statements": []}]}
    assert not analyse(no_statements).ok
    assert not analyse(answer(statement(art=None))).ok  # art is always filled


def test_passage_with_unmatched_quote_is_set_aside_with_its_statements():
    good = {"quote": "The patriicians applauded.",
            "statements": [statement(evaluative_expression="applauded")]}
    bad = {"quote": QUOTE.replace("laborious and tedious", "brilliant and moving"),
           "statements": [statement(), statement(polarity=claim("positive"))]}
    check = analyse({"passages": [bad, good]})
    assert check.ok
    assert [p["passage_id"] for p in check.result["passages"]] == ["p02"]  # numbering keeps its place
    failed, = check.result["failed"]
    assert failed["where"] == "p01" and failed["item"] == "passage" and failed["statements"] == 2
    assert "does not match any passage" in failed["errors"][0]
    assert failed["answer"] == bad  # what the model wrote is kept


def test_expression_outside_quote_fails_the_statement_only():
    check = analyse(answer(statement(), statement(evaluative_expression="patriicians applauded")))
    assert any("does not occur inside its quote" in e for e in item_errors(check))
    assert [s["statement_id"] for s in check.result["passages"][0]["statements"]] == ["p01-s01"]
    assert check.result["failed"][0]["where"] == "p01-s02"


def test_assumption_rules():
    no_assumption = answer(statement(criterion=claim("aesthetic value", "inferred", None)))
    assert any("needs an assumption" in e for e in item_errors(analyse(no_assumption)))
    blank = answer(statement(creator=claim("Mr. Hartley", "suggested", "  ")))
    assert any("needs an assumption" in e for e in item_errors(analyse(blank)))
    observed_with = answer(statement(polarity=claim("negative", "observed", "because")))
    assert any("must have assumption null" in e for e in item_errors(analyse(observed_with)))


def test_statement_needs_a_target():
    check = analyse(answer(statement(creator=None, work_title=None, work_genre=None)))
    assert any("no target" in e for e in item_errors(check))
    assert check.result["passages"][0]["statements"] == []


def test_art_other_needs_a_note():
    assert any("note must explain" in e for e in item_errors(analyse(answer(statement(art=claim("other"))))))
    assert not item_errors(analyse(answer(statement(art=claim("other"), note="A masque: music and drama."))))
    assert any("non-empty" in e for e in item_errors(analyse(answer(statement(note="")))))


def test_names_must_be_written_without_wrapping_marks():
    check = analyse(answer(statement(work_title=claim("_The Deluge_"))))
    assert any("without the surrounding" in e for e in item_errors(check))
    check = analyse(answer(statement(creator=claim(" Mr. Hartley"))))
    assert any("spaces at its start" in e for e in item_errors(check))
    # a closing quotation mark that belongs to the name is fine
    text = "By the Author of “The Curate.” A tedious book."
    st = statement(creator=claim("the Author of “The Curate.”"), evaluative_expression="tedious",
                   work_title=None, work_genre=claim("book"), art=claim("literature"))
    assert not item_errors(analyse(answer(st, quote="A tedious book."), text=text))


# ------------------------------------------------------------ analyst: flags


def test_observed_value_not_in_text_is_flagged_not_rejected():
    assert not analyse(answer(statement(creator=claim("Mr Hartley")))).flags  # punctuation ignored
    check = analyse(answer(statement(creator=claim("John Hartley"))))
    assert check.ok
    assert [f["flag"] for f in check.flags] == ["observed_not_found"]
    # the same value marked suggested is not flagged
    check = analyse(answer(statement(creator=claim("John Hartley", "suggested", "Known composer."))))
    assert check.ok and not check.flags


def test_repeats_and_order_are_flagged():
    later = "The patriicians applauded."
    st2 = statement(evaluative_expression="applauded", quoted_source=claim("The patriicians"))
    obj = {"passages": [{"quote": later, "statements": [st2]},
                        {"quote": QUOTE, "statements": [statement(), statement()]},
                        {"quote": QUOTE, "statements": [statement(polarity=claim("positive"))]}]}
    check = analyse(obj)
    assert check.ok, check.errors
    assert sorted(f["flag"] for f in check.flags) == ["passage_order", "repeated_quote", "repeated_statement"]


def test_ambiguous_quote_is_flagged():
    text = "A tedious book. A tedious book."
    st = statement(evaluative_expression="tedious", creator=None, work_title=None,
                   work_genre=claim("book"), art=claim("literature"))
    check = analyse(answer(st, quote="A tedious book."), text=text)
    assert check.ok and check.flags[0]["flag"] == "ambiguous_quote"


# ------------------------------------------------------------ reviewer


@pytest.fixture
def analysed():
    st2 = statement(evaluative_expression="the finest sacred work of the age",
                    polarity=claim("positive"), quoted_source=claim("a contemporary"),
                    work_genre=claim("oratorio", "inferred", "Said so in the heading."))
    check = analyse(answer(statement(), st2))
    assert check.ok and not check.result["failed"]
    return check.result


def review(actions, analysed):
    return checks.check_review(json.dumps({"actions": actions}), analysed, REVIEWER_SCHEMA)


def act(sid="p01-s01", field="statement", action="delete", new=None, reason="Not supported."):
    return {"statement_id": sid, "field": field, "action": action, "new_evidence": new, "reason": reason}


def test_no_actions_keeps_everything(analysed):
    check = review([], analysed)
    assert check.ok
    sts = check.result["passages"][0]["statements"]
    assert not any(s["deleted"] for s in sts)
    assert sts[0]["creator"]["review"] is None


def test_allowed_actions_are_applied_and_nothing_is_removed(analysed):
    check = review([act("p01-s01"),
                    act("p01-s02", "work_genre", "downgrade", "suggested", "Heading says nothing."),
                    act("p01-s02", "creator", "delete")], analysed)
    assert check.ok, check.errors
    s1, s2 = check.result["passages"][0]["statements"]
    assert s1["deleted"] and s1["deleted_reason"] == "Not supported."
    assert s1["creator"]["value"] == "Mr. Hartley"  # kept, only marked
    assert s2["work_genre"]["evidence"] == "suggested"
    assert s2["work_genre"]["evidence_analyst"] == "inferred"
    assert s2["work_genre"]["review"] == "downgraded"
    assert s2["creator"]["review"] == "deleted" and s2["creator"]["value"] == "Mr. Hartley"
    assert s2["evidence_analyst"] == "inferred" and s2["evidence"] == "suggested"
    # the analyst's result itself is unchanged
    assert "review" not in analysed["passages"][0]["statements"][1]["creator"]


def test_deleting_a_field_can_raise_the_statement_level_only_by_removal(analysed):
    check = review([act("p01-s02", "work_genre", "delete")], analysed)
    assert check.ok
    assert check.result["passages"][0]["statements"][1]["evidence"] == "observed"


@pytest.mark.parametrize("bad, expected", [
    (act("p09-s01"), "no statement"),
    (act("p01-s01", "polarity", "delete"), "cannot be deleted"),
    (act("p01-s02", "quoted_source", "delete"), "cannot be deleted"),
    (act("p01-s01", "quoted_source", "downgrade", "inferred"), "field is empty"),
    (act("p01-s01", "creator", "downgrade", None), "needs new_evidence"),
    (act("p01-s01", "creator", "delete", "inferred"), "new_evidence null"),
    (act("p01-s02", "work_genre", "downgrade", "inferred"), "does not lower"),
    (act("p01-s01", "statement", "downgrade", "inferred"), "cannot be downgraded"),
    (act(reason="   "), "reason is empty"),
])
def test_forbidden_actions_are_rejected(bad, expected, analysed):
    check = review([bad], analysed)
    assert not check.ok
    assert any(expected in e for e in check.errors), check.errors


def test_reviewer_cannot_add_or_rewrite(analysed):
    # A new value or a new statement cannot even be expressed: the schema rejects extra keys.
    rewrite = act("p01-s01", "polarity", "downgrade", "inferred")
    rewrite["new_value"] = "positive"
    assert any("format error" in e for e in review([rewrite], analysed).errors)
    raw = json.dumps({"actions": [], "statements": [statement()]})
    assert not checks.check_review(raw, analysed, REVIEWER_SCHEMA).ok
    assert not review([act(field="quote")], analysed).ok
    assert not review([act("p01-s01", "creator", "upgrade", "observed")], analysed).ok


def test_conflicting_actions_are_rejected(analysed):
    twice = [act("p01-s01", "creator", "delete"), act("p01-s01", "creator", "downgrade", "inferred")]
    assert any("second action" in e for e in review(twice, analysed).errors)
    after = [act("p01-s01"), act("p01-s01", "creator", "delete")]
    assert any("is deleted, so" in e for e in review(after, analysed).errors)
    before = [act("p01-s01", "creator", "delete"), act("p01-s01")]
    assert any("is deleted, so" in e for e in review(before, analysed).errors)


def test_reviewer_answer_must_be_bare_json(analysed):
    check = checks.check_review("```json\n{\"actions\": []}\n```", analysed, REVIEWER_SCHEMA)
    assert not check.ok and "code fences" in check.errors[0]


def test_reviewer_input_shows_only_the_analysts_fields(analysed):
    shown = json.loads(checks.reviewer_input(analysed))
    st = shown["passages"][0]["statements"][0]
    assert set(st) == {"statement_id", "evaluative_expression", "note", *checks.CLAIM_FIELDS}
    assert "quote_start" not in shown["passages"][0]


def test_retry_message_lists_errors():
    msg = checks.retry_message(["one", "two"])
    assert "- one\n- two" in msg and "JSON object only" in msg


def test_apply_review_does_not_modify_input(analysed):
    before = copy.deepcopy(analysed)
    checks.apply_review(analysed, [act()])
    assert analysed == before


def test_retry_message_after_cut_off_asks_not_to_repeat():
    assert "do not repeat yourself" not in checks.retry_message(["one"])
    assert "do not repeat yourself" in checks.retry_message(["one"], cut_off=True)
