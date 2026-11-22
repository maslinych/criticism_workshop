"""Tests for the annotation runner, with a fake LLM instead of the real service.

They check that answers are checked before acceptance, that rejected answers are
retried with feedback, that failures are recorded and never dropped, and above
all that a resumed run never pays again for work that is done.
"""

import json

import pytest

from ncse import annotate, checkreport
from ncse.config import load_config
from ncse.llm import LLMError, Reply

ARTICLE = "LDR-1851-05-17-011"  # the Don Giovanni notice in corpus_sample/
QUOTE = "It is familiar as household words, and yet eternally fresh!"


def good_answer():
    claim = lambda v: {"value": v, "evidence": "observed", "assumption": None}  # noqa: E731
    return json.dumps({"passages": [{"quote": QUOTE, "statements": [{
        "evaluative_expression": "eternally fresh", "creator": None, "art": claim("music"),
        "work_title": claim("Don Giovanni"), "work_genre": claim("opera"),
        "polarity": claim("positive"), "sarcastic": claim("no"), "criterion": claim("novelty"),
        "quoted_source": None, "note": None}]}]})


NOT_BARE = "Here is the annotation:\n" + good_answer()  # unusable as a whole: rejected and retried
UNMATCHED = good_answer().replace("household words", "a story told by an idiot")  # one passage fails


class FakeClient:
    """Returns scripted answers in order; records every request."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.requests = []

    def chat(self, model, messages, settings):
        self.requests.append(messages)
        item = self.answers.pop(0)
        if isinstance(item, BaseException):  # includes KeyboardInterrupt (Ctrl-C)
            raise item
        finish = "stop"
        if isinstance(item, tuple):  # (text, finish_reason)
            item, finish = item
        return Reply(text=item, finish_reason=finish, usage={"prompt_tokens": 100, "completion_tokens": 10},
                     response_id="r", model=model)


@pytest.fixture
def cfg(tmp_path):
    cfg = load_config()
    cfg["paths"]["annotation"] = tmp_path / "annotation"
    cfg["paths"]["logs"] = tmp_path / "logs"
    cfg["paths"]["reports"] = tmp_path / "reports"
    cfg["paths"]["reports"].mkdir()
    for step in ("analyst", "reviewer"):
        cfg["annotation"][step]["model"] = "fake-model"
    cfg["annotation"]["max_retries"] = 2
    cfg["annotation"]["concurrency"] = 1
    return cfg


def analyse(cfg, client, **kw):
    kw.setdefault("articles", [ARTICLE])
    return annotate.run(cfg, "analyst", sample=True, client=client, **kw)


def record(cfg, step="analyst", aid=ARTICLE):
    return annotate.load_record(annotate.output_folder(cfg, step, True), aid)


def test_accepted_answer_is_stored_with_provenance(cfg):
    client = FakeClient([good_answer()])
    analyse(cfg, client)
    rec = record(cfg)
    assert rec["status"] == "accepted" and rec["accepted_attempt"] == 1
    assert rec["corpus_version"] == "corpus-v1.0 sample"
    assert rec["prompt_version"] == "v1" and len(rec["prompt_sha256"]) == 64
    assert rec["model"] == "fake-model"
    assert rec["attempts"][0]["raw_response"] == good_answer()
    assert rec["attempts"][0]["usage"]["prompt_tokens"] == 100
    assert rec["result"]["passages"][0]["statements"][0]["statement_id"] == "p01-s01"
    # the article text went into the request unchanged
    user = client.requests[0][1]["content"]
    assert QUOTE in user and "Date of issue: 1851-05-17" in user


def test_rejected_answer_is_retried_with_feedback(cfg):
    client = FakeClient([NOT_BARE, good_answer()])
    summary = analyse(cfg, client)
    rec = record(cfg)
    assert rec["status"] == "accepted" and rec["accepted_attempt"] == 2
    assert not rec["attempts"][0]["accepted"]
    retry = client.requests[1]
    assert retry[2] == {"role": "assistant", "content": NOT_BARE}
    assert "single JSON object" in retry[3]["content"]
    assert summary["counts"]["retries"] == 1
    assert summary["counts"]["check failed: text around JSON"] == 1


def test_failed_items_are_set_aside_without_a_retry(cfg):
    client = FakeClient([UNMATCHED])
    summary = analyse(cfg, client)
    rec = record(cfg)
    assert len(client.requests) == 1
    assert rec["status"] == "accepted" and rec["result"]["passages"] == []
    failed, = rec["result"]["failed"]
    assert failed["where"] == "p01" and "does not match any passage" in failed["errors"][0]
    assert summary["counts"]["failed passages"] == 1
    assert summary["counts"]["item failed: quote not found"] == 1
    # the stored result is what the re-check produces
    checkreport.run(cfg, "analyst", sample=True)


def test_same_answer_twice_stops_the_retries(cfg):
    client = FakeClient(["not json", "not json", good_answer()])
    summary = analyse(cfg, client)
    rec = record(cfg)
    assert len(client.requests) == 2
    assert rec["status"] == "failed" and "same answer" in rec["errors"][0]
    assert summary["counts"]["retries stopped (answer repeated)"] == 1


def test_cut_off_answer_is_sent_back_shortened(cfg):
    # A model stuck in a loop until the length limit: only the beginning goes back.
    loop = "The fourth statement is about aesthetic value. " * 2000
    client = FakeClient([(loop, "length"), good_answer()])
    analyse(cfg, client)
    rec = record(cfg)
    assert rec["status"] == "accepted" and rec["accepted_attempt"] == 2
    assert rec["attempts"][0]["raw_response"] == loop  # the full answer is still kept
    echoed = client.requests[1][2]["content"]
    limit = cfg["annotation"]["retry_echo_chars"]
    assert echoed.startswith(loop[:limit]) and len(echoed) < limit + 200
    assert "left out" in echoed
    feedback = client.requests[1][3]["content"]
    assert "cut off" in feedback and "do not repeat yourself" in feedback


def test_short_cut_off_answer_is_sent_back_whole(cfg):
    client = FakeClient([('{"passages": [', "length"), good_answer()])
    analyse(cfg, client)
    assert client.requests[1][2]["content"] == '{"passages": ['


def test_failure_after_all_attempts_is_recorded(cfg):
    client = FakeClient(["not json", "not JSON", "{not json"])
    summary = analyse(cfg, client)
    rec = record(cfg)
    assert rec["status"] == "failed" and len(rec["attempts"]) == 3
    assert summary["counts"]["failed"] == 1
    # a second run does not touch it ...
    analyse(cfg, FakeClient([]))
    # ... unless asked to, and then the old attempts are kept
    analyse(cfg, FakeClient([good_answer()]), retry_failed=True)
    rec = record(cfg)
    assert rec["status"] == "accepted" and rec["accepted_attempt"] == 4


def test_finished_work_is_never_requested_again(cfg):
    analyse(cfg, FakeClient([good_answer()]))
    client = FakeClient([])  # any request would fail: the list is empty
    summary = analyse(cfg, client)
    assert client.requests == []
    assert summary["counts"]["skipped (already accepted)"] == 1


def test_answer_saved_but_not_checked_is_checked_on_resume(cfg):
    # Simulate a run that stopped right after the answer was saved.
    folder = annotate.output_folder(cfg, "analyst", True)
    annotate.save_record(folder, {
        "article_id": ARTICLE, "step": "analyst", "status": "in_progress", "corpus_version": "x",
        "attempts": [{"attempt": 1, "prompt_version": "v1", "prompt_sha256": "s", "model_requested": "fake-model",
                      "settings": {}, "raw_response": good_answer(), "answered_at": "t", "usage": {}}],
        "result": None, "flags": [], "errors": [], "run_ids": []})
    client = FakeClient([])
    analyse(cfg, client)
    assert client.requests == []
    assert record(cfg)["status"] == "accepted"


def test_interrupted_round_continues_where_it_stopped(cfg):
    client = FakeClient([NOT_BARE, LLMError("quota exceeded")])
    summary = analyse(cfg, client)
    assert summary["counts"]["stopped early"] == 1
    rec = record(cfg)
    assert rec["status"] == "in_progress" and len(rec["attempts"]) == 1
    client = FakeClient([good_answer()])
    analyse(cfg, client)
    assert len(client.requests) == 1
    assert client.requests[0][3]["role"] == "user"  # the retry carries the earlier feedback
    assert record(cfg)["accepted_attempt"] == 2


def test_ctrl_c_stops_the_run_and_keeps_finished_work(cfg):
    client = FakeClient([good_answer(), KeyboardInterrupt()])
    summary = analyse(cfg, client, articles=[ARTICLE, "LDR-1850-11-30-005"])
    assert summary["counts"]["stopped early"] == 1
    assert client.stop.is_set()  # the client's pauses end too
    done = [record(cfg, aid=a) for a in (ARTICLE, "LDR-1850-11-30-005")]
    assert [r["status"] for r in done if r] == ["accepted"]


def test_fatal_error_stops_before_other_articles(cfg):
    client = FakeClient([LLMError("wrong key")])
    analyse(cfg, client, articles=None, limit=3)
    assert len(client.requests) == 1


def test_missing_model_stops_before_any_request(cfg):
    cfg["annotation"]["analyst"]["model"] = None
    with pytest.raises(SystemExit, match="no model set"):
        analyse(cfg, FakeClient([]))


# ------------------------------------------------------------ reviewer


def test_review_flow_and_recheck_report(cfg):
    analyse(cfg, FakeClient([good_answer()]))
    deletion = json.dumps({"actions": [{"statement_id": "p01-s01", "field": "criterion", "action": "delete",
                                        "new_evidence": None, "reason": "x"}]})
    downgrade = json.dumps({"actions": [{"statement_id": "p01-s01", "field": "criterion",
                                         "action": "downgrade", "new_evidence": "inferred",
                                         "reason": "Freshness of a familiar work is not plainly novelty."}]})
    client = FakeClient([deletion, downgrade])
    annotate.run(cfg, "reviewer", sample=True, client=client, articles=[ARTICLE])
    rec = record(cfg, "reviewer")
    assert rec["status"] == "accepted" and rec["sent"] is True
    assert "cannot be deleted" in client.requests[1][3]["content"]
    # the reviewer was shown the statements with short identifiers
    assert '"statement_id": "p01-s01"' in client.requests[0][1]["content"]
    st = rec["result"]["passages"][0]["statements"][0]
    assert st["criterion"]["evidence"] == "inferred" and st["evidence"] == "inferred"

    checkreport.run(cfg, "analyst", sample=True)
    checkreport.run(cfg, "reviewer", sample=True)
    report = (cfg["paths"]["reports"] / "04-review-checks-sample.md").read_text()
    assert "criterion: downgraded observed→inferred" in report
    assert "**Re-check:** 0 problem(s)." in report


def test_article_without_statements_is_not_sent_to_reviewer(cfg):
    analyse(cfg, FakeClient(['{"passages": []}']))
    client = FakeClient([])
    annotate.run(cfg, "reviewer", sample=True, client=client, articles=[ARTICLE])
    assert client.requests == []
    rec = record(cfg, "reviewer")
    assert rec["status"] == "accepted" and rec["sent"] is False


def test_reviewer_skips_articles_without_accepted_analysis(cfg):
    client = FakeClient([])
    summary = annotate.run(cfg, "reviewer", sample=True, client=client, articles=[ARTICLE])
    assert client.requests == []
    assert summary["counts"]["skipped (no accepted analyst answer)"] == 1


def test_recheck_detects_a_changed_record(cfg):
    analyse(cfg, FakeClient([good_answer()]))
    folder = annotate.output_folder(cfg, "analyst", True)
    rec = record(cfg)
    rec["result"]["passages"][0]["statements"][0]["polarity"]["value"] = "negative"  # "hand edit"
    annotate.save_record(folder, rec)
    with pytest.raises(SystemExit, match="did not pass"):
        checkreport.run(cfg, "analyst", sample=True)
