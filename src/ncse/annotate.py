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
the model returns exactly the same answer twice in a row, no further attempt is
made. In an accepted analyst answer, passages and statements that break a rule
are set aside as failed items, with their reasons, and the rest is kept (D-027).
An article whose answer is accepted, or that has used up its attempts (failed),
is done: running the stage again skips it. `--retry-failed` gives failed
articles a new round of attempts; earlier attempts are kept.
"""

import csv
import datetime as dt
import hashlib
import json
import os
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import checks
from .llm import LLMClient, LLMError
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
    path = folder / f"{record['article_id']}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def result_sha256(result: dict) -> str:
    return hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- one step


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
        self.settings = {k: self.settings_cfg.get(k) for k in ("temperature", "max_tokens")}
        if self.settings_cfg.get("response_format"):
            self.settings["response_format"] = {"type": self.settings_cfg["response_format"]}
        self.max_attempts = 1 + ann["max_retries"]
        self.echo_chars = ann["retry_echo_chars"]
        self.tolerance = Tolerance.from_config(cfg.get("quotes"))
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
        self.client.stop = self.stop  # the client's pauses before a retry end when the run stops
        self.fatal: str | None = None

    def count(self, what: str, n: int = 1) -> None:
        with self.lock:
            self.log.count(what, n)

    def info(self, message: str) -> None:
        with self.lock:
            self.log.info(message)

    # -- which articles to send

    def todo(self, articles: list[dict], retry_failed: bool) -> list[tuple[dict, dict | None]]:
        """Articles still to be processed, with their existing record (if any)."""
        out = []
        for art in articles:
            aid = art["article_id"]
            record = load_record(self.out, aid)
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
            out.append((art, record))
        return out

    # -- one article

    def new_record(self, aid: str) -> dict:
        record = {"article_id": aid, "step": self.step, "status": "in_progress",
                  "corpus_version": self.version, "attempts": [], "result": None,
                  "flags": [], "errors": [], "run_ids": []}
        if self.step == "reviewer":
            analyst = load_record(self.analyst_out, aid)
            record["analyst_sha256"] = result_sha256(analyst["result"])
        return record

    def base_messages(self, art: dict, text: str) -> tuple[list[dict], dict | None]:
        values = {"periodical": art["periodical"], "issue_date": art["issue_date"],
                  "article_id": art["article_id"], "heading": art["heading"] or "(none)", "text": text}
        analyst_result = None
        if self.step == "reviewer":
            analyst_result = load_record(self.analyst_out, art["article_id"])["result"]
            values["statements_json"] = checks.reviewer_input(analyst_result)
        return self.prompt.render(**values), analyst_result

    def check(self, raw: str | None, text: str, analyst_result: dict | None) -> checks.CheckResult:
        if self.step == "analyst":
            return checks.check_analyst(raw, text, self.prompt.schema, self.tolerance)
        return checks.check_review(raw, analyst_result, self.prompt.schema)

    def process(self, art: dict, record: dict | None) -> None:
        if self.stop.is_set():
            return
        aid = art["article_id"]
        text = read_text(self.corpus, art)
        record = record or self.new_record(aid)
        record["run_ids"].append(self.run_id)
        base, analyst_result = self.base_messages(art, text)

        if self.step == "reviewer" and checks.statement_count(analyst_result) == 0:
            # Nothing to review: recorded as accepted with no actions, no request sent.
            record.update(status="accepted", sent=False, result=checks.apply_review(analyst_result, []),
                          prompt_version=self.prompt.version, model=None)
            save_record(self.out, record)
            self.count("accepted without request (no statements to review)")
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
        self.count("articles processed")
        while True:
            last = record["attempts"][-1] if len(record["attempts"]) > round_start else None
            if last is not None and "accepted" not in last:
                # An answer saved but not yet checked (the run stopped in between):
                # check it now instead of paying for a new one.
                self.evaluate(last, text, analyst_result)
                save_record(self.out, record)
            if last is not None and last["accepted"]:
                self.accept(record, last, text, analyst_result)
                return
            if self.repeated(record, round_start):
                # Asking again would most likely bring the same answer (D-027).
                record.update(status="failed", errors=[REPEATED] + last["errors"])
                save_record(self.out, record)
                self.count("failed")
                self.count("retries stopped (answer repeated)")
                self.info(f"{aid}: FAILED: {REPEATED}")
                return
            if len(record["attempts"]) - round_start >= self.max_attempts:
                break
            if self.stop.is_set():
                save_record(self.out, record)
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
            except LLMError as e:
                self.fatal = self.fatal or str(e)  # keep the first reason (e.g. Ctrl-C)
                self.stop.set()
                save_record(self.out, record)
                self.info(f"{aid}: stopping the run: {e}")
                return
            attempt.update(answered_at=now(), raw_response=reply.text, finish_reason=reply.finish_reason,
                           usage=reply.usage, response_id=reply.response_id, model_reported=reply.model)
            record["attempts"].append(attempt)
            save_record(self.out, record)  # the paid answer is safe before anything else happens
            self.count("requests")
            self.count("prompt tokens", reply.usage.get("prompt_tokens", 0))
            self.count("completion tokens", reply.usage.get("completion_tokens", 0))
            self.evaluate(attempt, text, analyst_result)
            save_record(self.out, record)
            if not attempt["accepted"]:
                errors = attempt["errors"]
                self.info(f"{aid}: attempt {attempt['attempt']} rejected: {'; '.join(errors[:3])}"
                          + (" …" if len(errors) > 3 else ""))

        record.update(status="failed", errors=record["attempts"][-1]["errors"])
        save_record(self.out, record)
        self.count("failed")
        self.info(f"{aid}: FAILED after {self.max_attempts} attempts")

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
        """Whether the last two answers of this round are exactly the same."""
        tries = record["attempts"][round_start:]
        return len(tries) >= 2 and tries[-1].get("raw_response") == tries[-2].get("raw_response")

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

    def evaluate(self, attempt: dict, text: str, analyst_result: dict | None) -> checks.CheckResult:
        """Run the checks on one stored answer and note the outcome in the attempt."""
        result = self.check(attempt["raw_response"], text, analyst_result)
        if attempt.get("finish_reason") == "length":
            result.errors.insert(0, "the answer was cut off because it reached the length limit")
        attempt.update(errors=result.errors, flags=result.flags, accepted=not result.errors)
        for e in result.errors:
            self.count(f"check failed: {error_kind(e)}")
        return result

    def accept(self, record: dict, attempt: dict, text: str, analyst_result: dict | None) -> None:
        result = self.check(attempt["raw_response"], text, analyst_result)  # pure, so same outcome
        record.update(status="accepted", result=result.result, flags=result.flags, errors=[],
                      prompt_version=attempt["prompt_version"], prompt_sha256=attempt["prompt_sha256"],
                      model=attempt["model_requested"], model_reported=attempt.get("model_reported"),
                      settings=attempt["settings"], accepted_attempt=attempt["attempt"],
                      accepted_at=attempt["answered_at"])
        if self.step == "reviewer":
            record["sent"] = True
        save_record(self.out, record)
        self.count("accepted")
        self.count("flags", len(result.flags))
        if self.step == "analyst":
            self.count("statements", checks.statement_count(result.result))
            for item in result.result["failed"]:
                self.count(f"failed {item['item']}s")
                for e in item["errors"]:
                    self.count(f"item failed: {error_kind(e)}")
            if result.result["failed"]:
                self.info(f"{record['article_id']}: accepted; {len(result.result['failed'])} item(s) set aside: "
                          + "; ".join(item["errors"][0] for item in result.result["failed"][:3])
                          + (" …" if len(result.result["failed"]) > 3 else ""))
        else:
            self.count("reviewer actions", len(result.answer["actions"]))

    # -- the whole step

    def run(self, articles: list[dict], retry_failed: bool = False, limit: int | None = None) -> dict:
        self.info(f"{self.step}: model {self.model}, prompt {self.prompt.version} "
                  f"(sha256 {self.prompt.sha256[:12]}), corpus {self.version}, output {self.out}")
        work = self.todo(articles, retry_failed)
        if limit is not None:
            work = work[:limit]
        self.info(f"{len(work)} article(s) to process")
        workers = self.cfg["annotation"].get("concurrency", 1)
        pool = ThreadPoolExecutor(max_workers=workers)
        try:
            for future in [pool.submit(self.process, art, rec) for art, rec in work]:
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


def error_kind(message: str) -> str:
    """A short category of a check error, for the counts in the log and report."""
    kinds = [("not a verbatim passage", "quote not found"), ("does not match any passage", "quote not found"),
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
