"""Tests for the quotation matcher and the checks of both LLM steps (stages 5 and 7)."""

import copy
import json

import pytest

from ncse import checks
from ncse.prompts import load_prompt
from ncse.quotes import contains, find_all, normalize

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


def analyse(obj, text=TEXT):
    raw = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return checks.check_analyst(raw, text, ANALYST_SCHEMA)


# ------------------------------------------------------------ quotation matching


def test_quote_matching_tolerates_only_whitespace():
    assert find_all(TEXT, QUOTE)  # line break in the text, space in the quote
    assert find_all(TEXT, "  laborious   and\ttedious ")
    assert not find_all(TEXT, "laborious and tedious performance,")  # punctuation differs
    assert not find_all(TEXT, "The patricians applauded.")  # OCR error "corrected"
    assert not find_all(TEXT, "the finest sacred work of the age,\" a judgement")  # quote mark changed
    assert not find_all(TEXT, "mr. hartley's")  # capitals differ


def test_quote_positions_point_into_the_original_text():
    (start, end), = find_all(TEXT, "laborious and tedious")
    assert TEXT[start:end] == "laborious and\ntedious"


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


def test_empty_answer_list_is_valid():
    check = analyse({"passages": []})
    assert check.ok and check.result == {"passages": []}


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


def test_quote_not_in_text_is_rejected():
    check = analyse(answer(quote=QUOTE.replace("laborious", "labourious")))
    assert any("not a verbatim passage" in e for e in check.errors)


def test_expression_outside_quote_is_rejected():
    check = analyse(answer(statement(evaluative_expression="patriicians applauded")))
    assert any("does not occur inside its quote" in e for e in check.errors)


def test_assumption_rules():
    no_assumption = answer(statement(criterion=claim("aesthetic value", "inferred", None)))
    assert any("needs an assumption" in e for e in analyse(no_assumption).errors)
    blank = answer(statement(creator=claim("Mr. Hartley", "suggested", "  ")))
    assert any("needs an assumption" in e for e in analyse(blank).errors)
    observed_with = answer(statement(polarity=claim("negative", "observed", "because")))
    assert any("must have assumption null" in e for e in analyse(observed_with).errors)


def test_statement_needs_a_target():
    check = analyse(answer(statement(creator=None, work_title=None, work_genre=None)))
    assert any("no target" in e for e in check.errors)


def test_art_other_needs_a_note():
    assert any("note must explain" in e for e in analyse(answer(statement(art=claim("other")))).errors)
    assert analyse(answer(statement(art=claim("other"), note="A masque: music and drama."))).ok
    assert any("non-empty" in e for e in analyse(answer(statement(note=""))).errors)


def test_names_must_be_written_without_wrapping_marks():
    check = analyse(answer(statement(work_title=claim("_The Deluge_"))))
    assert any("without the surrounding" in e for e in check.errors)
    check = analyse(answer(statement(creator=claim(" Mr. Hartley"))))
    assert any("spaces at its start" in e for e in check.errors)
    # a closing quotation mark that belongs to the name is fine
    text = "By the Author of “The Curate.” A tedious book."
    st = statement(creator=claim("the Author of “The Curate.”"), evaluative_expression="tedious",
                   work_title=None, work_genre=claim("book"), art=claim("literature"))
    assert analyse(answer(st, quote="A tedious book."), text=text).ok


# ------------------------------------------------------------ analyst: flags


def test_observed_value_not_in_text_is_flagged_not_rejected():
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
    assert check.ok
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
