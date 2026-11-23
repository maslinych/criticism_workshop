"""Stages 4 and 6: send articles to the analyst and the reviewer.

`uv run ncse analyse` sends each article of the prepared corpus to the analyst;
`uv run ncse review` sends each article with an accepted analyst answer to the
reviewer. `--sample` works on corpus_sample/ instead (sample mode).

For every article and step one *record* is kept, a JSON file in
data/annotation/<full|sample>/<step>/<article_id>.json. It holds every attempt:
the messages sent (apart from the instructions, which are identified by prompt
version and checksum), the raw answer exactly as returned, the token counts, and
the result of the checks. The record is saved right after every answer, before
anything else happens, so a paid answer is never lost.

Each answer is checked at once (checks.py). An answer that is unusable as a
whole (not a bare JSON object, wrong format, cut off) is rejected and retried,
at most `annotation.max_retries` times, with a message listing what failed. If
the model returns exactly the same (non-empty) answer twice in a row, no further
attempt is made. In an accepted analyst answer, passages and statements that break a rule
are set aside as failed items, with their reasons, and the rest is kept (D-027).
An article whose answer is accepted, or that has used up its attempts (failed),
is done: running the stage again skips it. `--retry-failed` gives failed
articles a new round of attempts; earlier attempts are kept.

A long article (over `annotation.max_part_chars` characters) is sent in parts,
one request per part, with the article's beginning and the text before the part
as context (parts.py, D-034). Each part has its own record, in
<step>/parts/<article_id>.part<k>of<n>.json, with its own attempts; when all
parts are done, their results are joined into the article's record, which then
looks like that of an article sent whole (positions and numbers over the whole
article), plus the list of parts and a summary of their attempts. The reviewer
reviews the same parts as the analyst. Resuming or `--retry-failed` sends only
the parts that are not yet accepted.
"""

import csv
import datetime as dt
import hashlib
import json
import os
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from . import checks, parts
from .llm import LLMClient, LLMError, SlowAnswer
from .prompts import load_prompt
from .quotes import Tolerance
from .runlog import RunLog

STEPS = ("analyst", "reviewer")
REPEATED = ("the model returned exactly the same answer as in the previous attempt, "
            "so no further attempts were made")


# ---------------------------------------------------------------- corpus


def corpus_folder(cfg: dict, sample: bool) -> Path:
    return cfg["paths"]["corpus_sample" if sample else "corpus"]


def corpus_version(cfg: dict, sample: bool) -> str:
    """Which corpus the annotations refer to (AGENTS.md 4, provenance)."""
    if sample:
        # corpus_sample/ was drawn from corpus-v1.0 (texts checked identical, D-025).
        return f"corpus-v{cfg['release']['version']} sample"
    folder = cfg["paths"]["corpus"]
    fetched, build = folder / "FETCHED.json", folder / "BUILD.json"
    if fetched.exists():
        return json.loads(fetched.read_text())["tag"]
    if build.exists():
        info = json.loads(build.read_text())
        return f"local build at {info['commit'][:7]}" + (" (uncommitted changes)" if info.get("dirty") else "")
    raise SystemExit(f"no prepared corpus in {folder}: run `uv run ncse fetch` first")


def load_articles(folder: Path) -> list[dict]:
    with open(folder / "metadata.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_text(folder: Path, article: dict) -> str:
    return (folder / "texts" / article["file_name"]).read_text(encoding="utf-8")


def output_folder(cfg: dict, step: str, sample: bool) -> Path:
    return cfg["paths"]["annotation"] / ("sample" if sample else "full") / step


# ---------------------------------------------------------------- records


def load_record(folder: Path, article_id: str) -> dict | None:
    path = folder / f"{article_id}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def save_record(folder: Path, record: dict) -> None:
    """Write via a temporary file, so an interruption never leaves half a record."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{record.get('record_name') or record['article_id']}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def result_sha256(result: dict) -> str:
    return hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- units


@dataclass
class Unit:
    """What one request is about: a whole article, or one part of a long one (D-034)."""

    art: dict
    number: int | None = None  # part number, from 1; None for a whole article
    count: int = 1             # number of parts of the article
    start: int = 0             # the part's position in the article text
    end: int | None = None

    @property
    def aid(self) -> str:
        return self.art["article_id"]

    @property
    def is_part(self) -> bool:
        return self.number is not None

    @property
    def name(self) -> str:
        return parts.part_name(self.aid, self.number, self.count) if self.is_part else self.aid

    @property
    def span(self) -> tuple[int, int] | None:
        return (self.start, self.end) if self.is_part else None


def accepted_actions(record: dict) -> list[dict]:
    """The reviewer actions of an accepted reviewer record (of an article or a part)."""
    if record.get("sent") is False:
        return []
    return json.loads(record["attempts"][record["accepted_attempt"] - 1]["raw_response"])["actions"]


def attempt_summary(attempt: dict, number: int) -> dict:
    """What an article's joined record keeps of one attempt for one of its parts;
    the full attempt stays in the part's record."""
    keep = ("attempt", "run_id", "prompt_version", "prompt_sha256", "model_requested", "requested_at",
            "answered_at", "finish_reason", "usage", "errors", "accepted")
    return {"part": number, **{k: attempt[k] for k in keep if k in attempt}}


# ---------------------------------------------------------------- one step


REASONING_EFFORT = ("none", "minimal", "low", "medium", "high")
# Request fields set by the code or by named settings; `extra` may not override them.
RESERVED = {"model", "messages", "stream", "temperature", "max_tokens", "response_format", "reasoning_effort"}


def request_settings(step_cfg: dict, step: str) -> dict:
    """The model settings sent with every request of one step (D-030). They are
    recorded with every attempt, so each answer's settings are known."""
    settings = {k: step_cfg.get(k) for k in ("temperature", "max_tokens")}
    if step_cfg.get("response_format"):
        settings["response_format"] = {"type": step_cfg["response_format"]}
    effort = step_cfg.get("reasoning_effort")
    if effort is not None:
        if effort not in REASONING_EFFORT:
            raise SystemExit(f"annotation.{step}.reasoning_effort must be one of "
                             f"{', '.join(REASONING_EFFORT)} or null, not {effort!r}")
        settings["reasoning_effort"] = effort
    extra = step_cfg.get("extra") or {}
    if not isinstance(extra, dict):
        raise SystemExit(f"annotation.{step}.extra must be a mapping of option names to values")
    clash = sorted(RESERVED & set(extra))
    if clash:
        raise SystemExit(f"annotation.{step}.extra may not set {', '.join(clash)}; "
                         "use the named settings in config.yaml for these")
    settings.update(extra)
    return settings


class StepRunner:
    """Runs one step (analyst or reviewer) over a list of articles."""

    def __init__(self, cfg: dict, step: str, sample: bool, client=None, log: RunLog | None = None):
        if step not in STEPS:
            raise ValueError(step)
        self.cfg, self.step, self.sample = cfg, step, sample
        ann = cfg["annotation"]
        self.settings_cfg = ann[step]
        self.model = self.settings_cfg["model"]
        if not self.model:
            raise SystemExit(f"no model set for the {step}: fill in annotation.{step}.model in config.yaml")
        self.settings = request_settings(self.settings_cfg, step)
        self.max_attempts = 1 + ann["max_retries"]
        self.echo_chars = ann["retry_echo_chars"]
        self.tolerance = Tolerance.from_config(cfg.get("quotes"))
        self.max_part_chars = ann.get("max_part_chars")  # None: never split (D-034)
        self.context_chars = (ann.get("context_opening_chars", 1500), ann.get("context_before_chars", 1500))
        self.join_lock = threading.Lock()
        self.prompt = load_prompt(step, self.settings_cfg["prompt_version"])
        self.corpus = corpus_folder(cfg, sample)
        self.version = corpus_version(cfg, sample)
        self.out = output_folder(cfg, step, sample)
        self.analyst_out = output_folder(cfg, "analyst", sample)
        self.log = log or RunLog(f"{'analyse' if step == 'analyst' else 'review'}{'-sample' if sample else ''}",
                                 cfg["paths"]["logs"])
        self.client = client or LLMClient.from_config(cfg, log=self.log.info)
        self.run_id = f"{step}-{dt.datetime.now():%Y%m%d-%H%M%S}"
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.slow_in_row = 0  # slow failures in a row (D-031)
        self.max_slow_in_row = ann.get("max_slow_in_row", 3)
        self.client.stop = self.stop  # the client's pauses before a retry end when the run stops
        self.fatal: str | None = None

    def count(self, what: str, n: int = 1) -> None:
        with self.lock:
            self.log.count(what, n)

    def info(self, message: str) -> None:
        with self.lock:
            self.log.info(message)

    # -- which articles to send

    def todo(self, articles: list[dict], retry_failed: bool) -> list[list[tuple[Unit, dict | None]]]:
        """For each article still to be processed, its units (the whole article,
        or the parts not yet accepted) with their existing records (if any)."""
        out = []
        for art in articles:
            aid = art["article_id"]
            record = load_record(self.out, aid)
            analyst = None
            if self.step == "reviewer":
                analyst = load_record(self.analyst_out, aid)
                if analyst is None or analyst["status"] != "accepted":
                    self.count("skipped (no accepted analyst answer)")
                    continue
                if record and record.get("analyst_sha256") != result_sha256(analyst["result"]):
                    self.count("skipped (review belongs to an older analyst answer)")
                    self.info(f"{aid}: the review was made for a different analyst answer; not changed")
                    continue
            if record and record["status"] == "accepted":
                self.count("skipped (already accepted)")
                continue
            if record and record["status"] == "failed" and not retry_failed:
                self.count("skipped (failed earlier; use --retry-failed)")
                continue
            spans = self.spans(art, analyst)
            if len(spans) == 1:
                out.append([(Unit(art), record)])
                continue
            units, stale = [], False
            for k, (start, end) in enumerate(spans, start=1):
                unit = Unit(art, k, len(spans), start, end)
                rec = load_record(self.out / "parts", unit.name)
                if rec and (rec["part"]["start"], rec["part"]["end"]) != (start, end):
                    raise SystemExit(f"{unit.name}: the stored part has other limits than the split now gives "
                                     "(was annotation.max_part_chars changed?); move the old records away first")
                if rec and analyst and rec.get("analyst_sha256") != result_sha256(analyst["result"]):
                    stale = True
                if rec and rec["status"] == "accepted":
                    continue
                if rec and rec["status"] == "failed" and not retry_failed:
                    continue
                units.append((unit, rec))
            if stale:
                self.count("skipped (review belongs to an older analyst answer)")
                self.info(f"{aid}: some parts were reviewed for a different analyst answer; not changed")
                continue
            if units:
                out.append(units)
            else:  # every part is done, but the run stopped before they were joined
                self.join(Unit(art, 1, len(spans)))
        return out

    def spans(self, art: dict, analyst: dict | None) -> list[tuple[int, int]]:
        """The parts of an article: the analyst splits by length; the reviewer
        uses the parts the analyst's answer was made from."""
        if self.step == "reviewer":
            found = analyst["result"].get("parts")
            return [(p["start"], p["end"]) for p in found] if found else [(0, None)]
        if not self.max_part_chars:
            return [(0, None)]
        return parts.split(read_text(self.corpus, art), self.max_part_chars)

    # -- one article

    def new_record(self, unit: Unit) -> dict:
        record = {"article_id": unit.aid, "step": self.step, "status": "in_progress",
                  "corpus_version": self.version, "attempts": [], "result": None,
                  "flags": [], "errors": [], "run_ids": []}
        if unit.is_part:
            record["record_name"] = unit.name
            record["part"] = {"number": unit.number, "count": unit.count, "start": unit.start, "end": unit.end}
        if self.step == "reviewer":
            analyst = load_record(self.analyst_out, unit.aid)
            record["analyst_sha256"] = result_sha256(analyst["result"])
        return record

    def folder(self, record: dict) -> Path:
        return self.out / "parts" if "part" in record else self.out

    def save(self, record: dict) -> None:
        save_record(self.folder(record), record)

    def tally(self, record: dict, what: str, n: int = 1) -> None:
        """Count an outcome, for a part ("part accepted") or an article ("accepted")."""
        self.count(("part " if "part" in record else "") + what, n)

    def base_messages(self, unit: Unit, text: str) -> tuple[list[dict], dict | None]:
        art = unit.art
        values = {"periodical": art["periodical"], "issue_date": art["issue_date"],
                  "article_id": art["article_id"], "heading": art["heading"] or "(none)",
                  "text": text[unit.start:unit.end] if unit.is_part else text}
        if unit.is_part:
            values.update(part_number=str(unit.number), part_count=str(unit.count),
                          context=parts.context(text, unit.start, *self.context_chars))
        analyst_result = None
        if self.step == "reviewer":
            analyst_result = load_record(self.analyst_out, art["article_id"])["result"]
            if unit.is_part:
                analyst_result = parts.part_of_analyst(analyst_result, unit.number)
            values["statements_json"] = checks.reviewer_input(analyst_result)
        return self.prompt.render(part=unit.is_part, **values), analyst_result

    def check(self, raw: str | None, text: str, analyst_result: dict | None,
              span: tuple[int, int] | None = None) -> checks.CheckResult:
        if self.step == "analyst":
            return checks.check_analyst(raw, text, self.prompt.schema, self.tolerance, span)
        return checks.check_review(raw, analyst_result, self.prompt.schema)

    def work(self, unit: Unit, record: dict | None) -> None:
        """Process one unit; after the last part of a long article, join the parts."""
        self.process(unit, record)
        if unit.is_part:
            self.join(unit)

    def process(self, unit: Unit, record: dict | None) -> None:
        if self.stop.is_set():
            return
        aid, span = unit.name, unit.span
        text = read_text(self.corpus, unit.art)
        record = record or self.new_record(unit)
        record["run_ids"].append(self.run_id)
        base, analyst_result = self.base_messages(unit, text)

        if self.step == "reviewer" and checks.statement_count(analyst_result) == 0:
            # Nothing to review: recorded as accepted with no actions, no request sent.
            record.update(status="accepted", sent=False, result=checks.apply_review(analyst_result, []),
                          prompt_version=self.prompt.version, model=None)
            self.save(record)
            self.tally(record, "accepted without request (no statements to review)")
            return

        # A new round: earlier attempts (from a run that stopped, or failed ones
        # being retried) are kept; the round gets max_attempts fresh tries,
        # except an unfinished round, which continues where it stopped.
        if record["status"] == "failed":
            record["status"] = "in_progress"
            round_start = len(record["attempts"])
        else:
            round_start = record.get("round_start", 0)
        record["round_start"] = round_start
        self.count("parts processed" if unit.is_part else "articles processed")
        while True:
            last = record["attempts"][-1] if len(record["attempts"]) > round_start else None
            if last is not None and "accepted" not in last:
                # An answer saved but not yet checked (the run stopped in between):
                # check it now instead of paying for a new one.
                self.evaluate(last, text, analyst_result, span)
                self.save(record)
            if last is not None and last["accepted"]:
                self.accept(record, last, text, analyst_result, span)
                return
            if self.repeated(record, round_start):
                # Asking again would most likely bring the same answer (D-027).
                record.update(status="failed", errors=[REPEATED] + last["errors"])
                self.save(record)
                self.tally(record, "failed")
                self.count("retries stopped (answer repeated)")
                self.info(f"{aid}: FAILED: {REPEATED}")
                return
            if len(record["attempts"]) - round_start >= self.max_attempts:
                break
            if self.stop.is_set():
                self.save(record)
                return
            messages = list(base)
            if last is not None:
                messages += [{"role": "assistant", "content": self.echo(last)},
                             {"role": "user", "content": checks.retry_message(
                                 last["errors"], cut_off=last.get("finish_reason") == "length")}]
                self.count("retries")
            attempt = {"attempt": len(record["attempts"]) + 1, "run_id": self.run_id,
                       "prompt_version": self.prompt.version, "prompt_sha256": self.prompt.sha256,
                       "model_requested": self.model, "settings": self.settings,
                       "messages_after_system": messages[1:], "requested_at": now()}
            try:
                reply = self.client.chat(self.model, messages, self.settings)
            except SlowAnswer as e:
                self.too_slow(record, attempt["requested_at"], str(e))
                return
            except LLMError as e:
                self.fatal = self.fatal or str(e)  # keep the first reason (e.g. Ctrl-C)
                self.stop.set()
                self.save(record)
                self.info(f"{aid}: stopping the run: {e}")
                return
            with self.lock:
                self.slow_in_row = 0
            attempt.update(answered_at=now(), raw_response=reply.text, finish_reason=reply.finish_reason,
                           usage=reply.usage, response_id=reply.response_id, model_reported=reply.model)
            if reply.reasoning:
                attempt["reasoning"] = reply.reasoning
            record["attempts"].append(attempt)
            self.save(record)  # the paid answer is safe before anything else happens
            self.count("requests")
            self.count("prompt tokens", reply.usage.get("prompt_tokens", 0))
            self.count("completion tokens", reply.usage.get("completion_tokens", 0))
            details = reply.usage.get("completion_tokens_details") or {}
            self.count("reasoning tokens (part of completion)", details.get("reasoning_tokens") or 0)
            self.evaluate(attempt, text, analyst_result, span)
            self.save(record)
            if not attempt["accepted"]:
                errors = attempt["errors"]
                self.info(f"{aid}: attempt {attempt['attempt']} rejected: {'; '.join(errors[:3])}"
                          + (" …" if len(errors) > 3 else ""))

        record.update(status="failed", errors=record["attempts"][-1]["errors"])
        self.save(record)
        self.tally(record, "failed")
        self.info(f"{aid}: FAILED after {self.max_attempts} attempts")

    def too_slow(self, record: dict, requested_at: str, message: str) -> None:
        """The service gave up on this article after a long wait (D-031). It is
        marked failed at once, since asking again would take as long and fail
        the same way; `--retry-failed` tries it again later. Only after
        `max_slow_in_row` such failures in a row does the run stop."""
        aid = record.get("record_name") or record["article_id"]
        record.setdefault("slow_failures", []).append({"requested_at": requested_at, "failed_at": now(),
                                                       "model": self.model, "error": message})
        record.update(status="failed", errors=[message])
        self.save(record)
        self.tally(record, "failed")
        self.tally(record, "failed (too slow for the service)")
        self.info(f"{aid}: FAILED: {message}")
        with self.lock:
            self.slow_in_row += 1
            if self.slow_in_row >= self.max_slow_in_row and not self.stop.is_set():
                self.fatal = self.fatal or (f"{self.slow_in_row} articles in a row were too slow for the service; "
                                            "turn reasoning down or choose a faster model in config.yaml")
                self.stop.set()

    def join(self, unit: Unit) -> None:
        """When every part of an article is done (accepted or failed), write the
        article's record from the parts' records (D-034). The article is
        accepted only if all its parts are; a failed article lists the failed
        parts, and `--retry-failed` sends only those again."""
        with self.join_lock:
            records = [load_record(self.out / "parts", parts.part_name(unit.aid, k, unit.count))
                       for k in range(1, unit.count + 1)]
            if any(r is None or r["status"] not in ("accepted", "failed") for r in records):
                return  # a part is still to be done (another thread, or a later run)
            record = join_records(self.step, records, load_record(self.analyst_out, unit.aid)
                                  if self.step == "reviewer" else None)
            save_record(self.out, record)
            if record["status"] == "accepted":
                self.count("accepted")
                self.count("accepted (long articles, in parts)")
            else:
                self.count("failed")
                self.info(f"{unit.aid}: FAILED: {'; '.join(record['errors'][:3])}")

    def interrupted(self, pool: ThreadPoolExecutor) -> None:
        """Ctrl-C: send no new request, stop any pause before a retry, and let
        requests already sent finish, so that answers being paid for are saved.
        A second Ctrl-C quits at once; answers still on their way are lost."""
        self.fatal = "interrupted with Ctrl-C"
        self.stop.set()
        self.info("Ctrl-C: no new requests will be sent. Waiting for the requests already sent, so that "
                  "their answers are saved. Press Ctrl-C again to quit at once (their answers would be lost).")
        try:
            pool.shutdown(wait=True, cancel_futures=True)
        except KeyboardInterrupt:
            self.info("quitting at once. Finished work is saved; run the same command again to continue.")
            self.log.close()
            os._exit(130)  # worker threads may still be waiting for the service

    @staticmethod
    def repeated(record: dict, round_start: int) -> bool:
        """Whether the last two answers of this round are exactly the same.
        Empty answers do not count: they come from the model's reasoning running
        in a loop until it stops, which happens at random, so a retry may well
        succeed."""
        tries = record["attempts"][round_start:]
        return (len(tries) >= 2 and bool((tries[-1].get("raw_response") or "").strip())
                and tries[-1].get("raw_response") == tries[-2].get("raw_response"))

    def echo(self, attempt: dict) -> str:
        """The rejected answer as it is sent back with a retry.

        An answer cut off at the length limit is often the model repeating itself
        until it ran out of room. Sending all of it back would make the retry
        long, expensive and likely to repeat the same loop, so only its beginning
        is sent (`annotation.retry_echo_chars`, D-026). Other answers are sent
        back whole: they are bounded by max_tokens and the model needs them to
        correct its quotes.
        """
        text = attempt["raw_response"] or ""
        if attempt.get("finish_reason") != "length" or len(text) <= self.echo_chars:
            return text
        return (text[:self.echo_chars]
                + f"\n\n[… the rest of this answer ({len(text) - self.echo_chars} more characters) is left out: "
                  "it was cut off at the length limit …]")

    def evaluate(self, attempt: dict, text: str, analyst_result: dict | None,
                 span: tuple[int, int] | None = None) -> checks.CheckResult:
        """Run the checks on one stored answer and note the outcome in the attempt."""
        result = self.check(attempt["raw_response"], text, analyst_result, span)
        if attempt.get("finish_reason") == "length":
            result.errors.insert(0, "the answer was cut off because it reached the length limit")
        attempt.update(errors=result.errors, flags=result.flags, accepted=not result.errors)
        for e in result.errors:
            self.count(f"check failed: {error_kind(e)}")
        return result

    def accept(self, record: dict, attempt: dict, text: str, analyst_result: dict | None,
               span: tuple[int, int] | None = None) -> None:
        result = self.check(attempt["raw_response"], text, analyst_result, span)  # pure, so same outcome
        record.update(status="accepted", result=result.result, flags=result.flags, errors=[],
                      prompt_version=attempt["prompt_version"], prompt_sha256=attempt["prompt_sha256"],
                      model=attempt["model_requested"], model_reported=attempt.get("model_reported"),
                      settings=attempt["settings"], accepted_attempt=attempt["attempt"],
                      accepted_at=attempt["answered_at"])
        if self.step == "reviewer":
            record["sent"] = True
        self.save(record)
        self.tally(record, "accepted")
        self.count("flags", len(result.flags))
        if self.step == "analyst":
            self.count("statements", checks.statement_count(result.result))
            for item in result.result["failed"]:
                self.count(f"failed {item['item']}s")
                for e in item["errors"]:
                    self.count(f"item failed: {error_kind(e)}")
            if result.result["failed"]:
                self.info(f"{record.get('record_name') or record['article_id']}: accepted; {len(result.result['failed'])} item(s) set aside: "
                          + "; ".join(item["errors"][0] for item in result.result["failed"][:3])
                          + (" …" if len(result.result["failed"]) > 3 else ""))
        else:
            self.count("reviewer actions", len(result.answer["actions"]))

    # -- the whole step

    def run(self, articles: list[dict], retry_failed: bool = False, limit: int | None = None) -> dict:
        self.info(f"{self.step}: model {self.model}, prompt {self.prompt.version} "
                  f"(sha256 {self.prompt.sha256[:12]}), corpus {self.version}, output {self.out}")
        groups = self.todo(articles, retry_failed)
        if limit is not None:
            groups = groups[:limit]
        work = [unit for group in groups for unit in group]
        n_parts = sum(1 for unit, _ in work if unit.is_part)
        self.info(f"{len(groups)} article(s) to process"
                  + (f", {n_parts} request(s) of them for parts of long articles" if n_parts else ""))
        workers = self.cfg["annotation"].get("concurrency", 1)
        pool = ThreadPoolExecutor(max_workers=workers)
        try:
            for future in [pool.submit(self.work, unit, rec) for unit, rec in work]:
                future.result()  # re-raise programming errors
        except KeyboardInterrupt:
            self.interrupted(pool)
        pool.shutdown(wait=True)
        if self.fatal:
            self.info(f"run stopped early: {self.fatal}. Finished work is saved; run the same command again to continue.")
            self.count("stopped early")
        summary = self.log.close()
        runs = self.out.parent / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        (runs / f"{self.run_id}.json").write_text(json.dumps({
            "run_id": self.run_id, "step": self.step, "corpus_version": self.version,
            "prompt_version": self.prompt.version, "prompt_sha256": self.prompt.sha256,
            "model": self.model, "settings": self.settings, "max_attempts": self.max_attempts,
            "log": str(self.log.path), **summary}, ensure_ascii=False, indent=1) + "\n")
        return summary


def join_records(step: str, records: list[dict], analyst: dict | None = None) -> dict:
    """The record of a long article, joined from the records of its parts (all
    done, in order). Pure: checkreport.py rebuilds it to confirm the stored one."""
    first = records[0]
    record = {"article_id": first["article_id"], "step": step, "corpus_version": first["corpus_version"],
              "parts": [{"record": r["record_name"], **r["part"], "status": r["status"]} for r in records],
              "attempts": [attempt_summary(a, r["part"]["number"]) for r in records for a in r["attempts"]],
              "run_ids": sorted({i for r in records for i in r["run_ids"]}),
              "flags": [], "errors": [], "result": None}
    if step == "reviewer":
        record["analyst_sha256"] = first["analyst_sha256"]
    failed = [r for r in records if r["status"] != "accepted"]
    if failed:
        record["status"] = "failed"
        record["errors"] = [f"part {r['part']['number']} of {r['part']['count']}: {e}"
                            for r in failed for e in r["errors"]]
        return record
    sent = [r for r in records if r.get("sent", True)]
    model_of = sent[0] if sent else first
    record.update(status="accepted", prompt_version=model_of.get("prompt_version"),
                  prompt_sha256=model_of.get("prompt_sha256"), model=model_of.get("model"),
                  model_reported=model_of.get("model_reported"), settings=model_of.get("settings"),
                  accepted_at=max((r["accepted_at"] for r in sent), default=None))
    versions = {(r.get("prompt_sha256"), r.get("model")) for r in sent}
    if len(versions) > 1:
        record["mixed_versions"] = sorted(f"{m} / {sha and sha[:12]}" for sha, m in versions)
    if step == "analyst":
        record["result"], record["flags"] = parts.join_analyst(
            [{"part": r["part"]["number"], "start": r["part"]["start"], "end": r["part"]["end"],
              "result": r["result"], "flags": r["flags"]} for r in records])
    else:
        record["sent"] = bool(sent)
        record["result"] = checks.apply_review(analyst["result"],
                                               [a for r in records for a in accepted_actions(r)])
    return record


def error_kind(message: str) -> str:
    """A short category of a check error, for the counts in the log and report."""
    kinds = [("gave up after waiting", "too slow for the service"), ("not a verbatim passage", "quote not found"), ("does not match any passage", "quote not found"),
             ("same answer as in the previous attempt", "answer repeated"),
             ("does not occur inside its quote", "expression not in quote"),
             ("needs an assumption", "assumption missing"),
             ("must have assumption null", "assumption on observed claim"),
             ("no target", "no target"), ("art is 'other'", "note missing for other"),
             ("format error", "format (schema)"), ("not valid JSON", "not JSON"),
             ("code fences", "code fences"), ("single JSON object", "text around JSON"),
             ("cut off", "answer cut off"), ("empty", "empty"),
             ("without the surrounding", "wrapped value"), ("spaces at its start", "spaces around value"),
             ("cannot be deleted", "deletion not allowed"), ("does not lower", "level not lowered"),
             ("no statement", "unknown statement"), ("second action", "two actions on one field"),
             ("is deleted, so", "action on deleted statement"),
             ("cannot be downgraded", "statement downgraded"), ("new_evidence", "new_evidence wrong")]
    for needle, kind in kinds:
        if needle in message:
            return kind
    return "other"


def run(cfg: dict, step: str, sample: bool = False, limit: int | None = None,
        articles: list[str] | None = None, retry_failed: bool = False, client=None) -> dict:
    runner = StepRunner(cfg, step, sample, client=client)
    rows = load_articles(runner.corpus)
    if articles:
        wanted = set(articles)
        unknown = wanted - {r["article_id"] for r in rows}
        if unknown:
            raise SystemExit(f"unknown article(s): {', '.join(sorted(unknown))}")
        rows = [r for r in rows if r["article_id"] in wanted]
    return runner.run(rows, retry_failed=retry_failed, limit=limit)
