"""Tests for long articles sent in parts (D-034): splitting, context, joining,
and the runner with a fake LLM (parts sent, joined, resumed, re-checked)."""

import json

import pytest

from ncse import annotate, checkreport, parts
from ncse.config import load_config
from ncse.llm import Reply, SlowAnswer

LONG = "LDR-1850-11-30-005"  # 9,873 characters: two parts at 6,000
Q1 = "An untrodden path remains open, and LORD CARLISLE is the first to venture on it."  # part 1
Q2 = "And comic it is, with a liberal allowance for the peculiarities of German vivacity."  # part 2


# ---------------------------------------------------------------- pure functions


def test_short_article_is_one_part():
    assert parts.split("A short notice.", 100) == [(0, 15)]


def test_parts_cover_the_text_within_the_limit_at_paragraph_breaks():
    paras = [f"Paragraph {i} " + "word " * 30 + "end." for i in range(12)]
    text = "\n\n".join(paras)
    spans = parts.split(text, 600)
    assert spans[0][0] == 0 and spans[-1][1] == len(text)
    assert all(a[1] == b[0] for a, b in zip(spans, spans[1:]))  # no gap, no overlap
    assert all(end - start <= 600 for start, end in spans)
    assert all(text[start].startswith("P") for start, _ in spans)  # each part starts a paragraph
    assert len(spans) == -(-len(text) // 600)  # the smallest number of parts
    assert parts.split(text, 600) == spans  # the same every time


def test_blank_line_after_a_sentence_is_preferred():
    # The mid-sentence break (a text box ending) is nearer the middle, but the
    # break after a full stop is chosen.
    text = "One two three four five six seven.\n\nMid sentence goes on and on-\n\n" + "on and on " * 4 + "end."
    (_, cut), _ = parts.split(text, 80)
    assert text[cut:].startswith("Mid")


def test_text_without_breaks_is_still_split():
    text = "x" * 2500
    spans = parts.split(text, 1000)
    assert len(spans) == 3 and all(e - s <= 1000 for s, e in spans)


def test_context_is_the_beginning_and_the_text_before_the_part():
    text = " ".join(f"w{i}" for i in range(2000))
    assert parts.context(text, 0, 100, 100) == ""
    assert parts.context(text, 150, 100, 100) == text[:150].rstrip()
    ctx = parts.context(text, 5000, 100, 100)
    head, tail = ctx.split(parts.GAP)
    assert text.startswith(head) and len(head) <= 100
    assert text[:5000].rstrip().endswith(tail) and len(tail) <= 100


def test_renumber():
    assert parts.renumber("p03", 4) == "p07"
    assert parts.renumber("p03-s02", 10) == "p13-s02"
    assert parts.renumber("statement p03-s02, creator: p01 stays", 1) == "statement p04-s02, creator: p01 stays"
    assert parts.renumber("p03", 0) == "p03"


def test_join_numbers_on_and_shifts_positions():
    def res(n_ok, n_failed):
        return {"passages": [{"passage_id": f"p{i:02d}", "quote_start": 10, "quote_end": 20,
                              "statements": [{"statement_id": f"p{i:02d}-s01"}]} for i in range(1, n_ok + 1)],
                "failed": [{"where": f"p{n_ok + 1:02d}", "item": "passage",
                            "errors": [f"passage p{n_ok + 1:02d}: the quote does not match"]}] * n_failed,
                "quote_tolerance": {"max_char_errors": 3, "max_error_share": 0.05}}
    joined, flags = parts.join_analyst([
        {"part": 1, "start": 0, "end": 100, "result": res(2, 1), "flags": []},
        {"part": 2, "start": 100, "end": 180, "result": res(1, 0),
         "flags": [{"where": "p01-s01", "flag": "repeated_statement", "detail": "identical to p01-s01"}]}])
    ids = [p["passage_id"] for p in joined["passages"]]
    assert ids == ["p01", "p02", "p04"]  # p03 is part 1's failed passage, which keeps its number
    assert joined["passages"][2]["statements"][0]["statement_id"] == "p04-s01"
    assert joined["passages"][2]["quote_start"] == 110 and joined["passages"][2]["part"] == 2
    assert joined["failed"][0]["where"] == "p03" and joined["failed"][0]["part"] == 1
    assert flags == [{"where": "p04-s01", "flag": "repeated_statement", "detail": "identical to p04-s01", "part": 2}]
    assert joined["parts"] == [{"part": 1, "start": 0, "end": 100}, {"part": 2, "start": 100, "end": 180}]


# ---------------------------------------------------------------- the runner


def answer(*quotes):
    claim = lambda v: {"value": v, "evidence": "observed", "assumption": None}  # noqa: E731
    return json.dumps({"passages": [{"quote": q, "statements": [{
        "evaluative_expression": q.split()[1], "creator": claim("someone"), "art": claim("literature"),
        "work_title": None, "work_genre": None, "polarity": claim("positive"), "sarcastic": claim("no"),
        "criterion": claim("aesthetic value"), "quoted_source": None, "note": None}]} for q in quotes]})


def review(*actions):
    return json.dumps({"actions": [{"statement_id": sid, "field": "statement", "action": "delete",
                                    "new_evidence": None, "reason": "not an evaluation"} for sid in actions]})


class FakeClient:
    def __init__(self, answers):
        self.answers, self.requests = list(answers), []

    def chat(self, model, messages, settings):
        self.requests.append(messages)
        item = self.answers.pop(0)
        if isinstance(item, BaseException):
            raise item
        return Reply(text=item, finish_reason="stop", usage={"prompt_tokens": 100, "completion_tokens": 10},
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
    cfg["annotation"].update(max_retries=2, concurrency=1, max_part_chars=6000)
    return cfg


def run(cfg, step, client, **kw):
    return annotate.run(cfg, step, sample=True, client=client, articles=[LONG], **kw)


def record(cfg, step="analyst"):
    return annotate.load_record(annotate.output_folder(cfg, step, True), LONG)


def test_long_article_is_sent_in_parts_and_joined(cfg):
    client = FakeClient([answer(Q1), answer(Q2, Q1)])  # part 2 also quotes part 1: set aside
    summary = run(cfg, "analyst", client)
    rec = record(cfg)
    assert rec["status"] == "accepted" and len(rec["parts"]) == 2
    text = (cfg["paths"]["corpus_sample"] / "texts" / f"{LONG}.txt").read_text(encoding="utf-8")
    (s1, e1), (s2, e2) = parts.split(text, 6000)
    # part 2's request carries only part 2 as the text to annotate, with context before it
    user = client.requests[1][1]["content"]
    assert "part 2 of 2" in user and Q2 in user.split("<<<PART\n")[1]
    assert Q1 in user.split("<<<CONTEXT\n")[1].split("\nCONTEXT>>>")[0]
    assert text[s2:e2].strip()[:200] in user
    # the joined result is numbered and positioned over the whole article
    p1, p2 = rec["result"]["passages"]
    assert (p1["passage_id"], p1["part"], p2["passage_id"], p2["part"]) == ("p01", 1, "p02", 2)
    assert text[p2["quote_start"]:p2["quote_end"]] == Q2
    failed, = rec["result"]["failed"]
    assert failed["where"] == "p03" and failed["part"] == 2 and "this part of the article" in failed["errors"][0]
    assert len(rec["attempts"]) == 2 and "raw_response" not in rec["attempts"][0]  # summaries only
    assert summary["counts"]["accepted"] == 1 and summary["counts"]["part accepted"] == 2
    checkreport.run(cfg, "analyst", sample=True)  # the joined record passes the re-check

    # the reviewer reviews the same parts, each with its own statements
    client = FakeClient([review("p01-s01"), review()])
    run(cfg, "reviewer", client)
    rev = record(cfg, "reviewer")
    assert rev["status"] == "accepted" and len(rev["parts"]) == 2
    first = client.requests[0][1]["content"].split("<<<STATEMENTS\n")[1]
    assert '"p01-s01"' in first and '"p02-s01"' not in first
    deleted = [s["deleted"] for p in rev["result"]["passages"] for s in p["statements"]]
    assert deleted == [True, False]
    checkreport.run(cfg, "reviewer", sample=True)


def test_a_failed_part_fails_the_article_and_only_it_is_retried(cfg):
    client = FakeClient([answer(Q1), SlowAnswer("the service gave up after waiting 300 s (HTTP 502)")])
    run(cfg, "analyst", client)
    rec = record(cfg)
    assert rec["status"] == "failed" and rec["errors"][0].startswith("part 2 of 2: the service gave up")
    checkreport.run(cfg, "analyst", sample=True)

    client = FakeClient([])
    run(cfg, "analyst", client)  # failed: skipped without --retry-failed
    assert client.requests == []

    client = FakeClient([answer(Q2)])
    run(cfg, "analyst", client, retry_failed=True)
    assert len(client.requests) == 1 and "part 2 of 2" in client.requests[0][1]["content"]
    rec = record(cfg)
    assert rec["status"] == "accepted" and [p["part"] for p in rec["result"]["passages"]] == [1, 2]


def test_parts_done_but_not_joined_are_joined_on_the_next_run(cfg):
    run(cfg, "analyst", FakeClient([answer(Q1), answer(Q2)]))
    folder = annotate.output_folder(cfg, "analyst", True)
    (folder / f"{LONG}.json").unlink()  # as if the run had stopped just before joining
    client = FakeClient([])
    run(cfg, "analyst", client)
    assert client.requests == [] and record(cfg)["status"] == "accepted"


def test_changed_limit_is_refused(cfg):
    run(cfg, "analyst", FakeClient([answer(Q1), SlowAnswer("too slow")]))
    cfg["annotation"]["max_part_chars"] = 5000
    with pytest.raises(SystemExit, match="other limits"):
        run(cfg, "analyst", FakeClient([]), retry_failed=True)
