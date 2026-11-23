"""Does the LLM service give the same answer to the same request at temperature 0?

The reviewer's actions differed a lot between two runs on the same analyst
answers (STATUS.md, 2026-11-23). This test tells whether that variation can be
removed by settings, or must be lived with.

It takes requests already made and stored (the first attempt of an accepted
record in data/annotation/sample/<step>/), sends each one again, unchanged,
several times, one after another, and compares the answers with each other and
with the stored one. It does this twice: with the step's settings from
config.yaml (temperature 0), and with the same settings plus a fixed `seed`,
which some services need before they repeat themselves.

Nothing in data/annotation/sample/ is changed. The answers are kept in
data/annotation/sample/temperature-test/<date>.json; a summary is printed.

Usage (from the project folder, with LITELLM_BASE_URL and LITELLM_API_KEY set):
    uv run python scripts/temperature_test.py                 # reviewer, 3 short articles, 3 repeats
    uv run python scripts/temperature_test.py --step analyst --articles MRP-1837-08-01-006 --repeats 2
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ncse.annotate import load_record, output_folder  # noqa: E402
from ncse.config import load_config  # noqa: E402
from ncse.llm import LLMClient, LLMError  # noqa: E402
from ncse.prompts import load_prompt  # noqa: E402

# Short articles, about 1 minute per reviewer request: two where the reviewer acted
# in the second pilot (3 actions each), one where it did not although an earlier
# run downgraded a creator there (12 statements, 0 actions).
DEFAULT_ARTICLES = ["LDR-1851-05-17-011", "MRP-1832-11-02-003", "MRP-1837-08-01-006"]
SEED = 1850


def content(step: str, raw: str | None) -> list | None:
    """What matters in an answer, in a fixed order, so that two answers that differ
    only in wording of reasons (reviewer) or of notes (analyst) can be told apart
    from answers that differ in substance. None if the answer is not usable JSON."""
    try:
        answer = json.loads(raw or "")
    except json.JSONDecodeError:
        return None
    if step == "reviewer":
        return sorted([a.get("statement_id"), a.get("field"), a.get("action"), a.get("new_evidence")]
                      for a in answer.get("actions", []))
    value = lambda c: (c or {}).get("value") if isinstance(c, dict) else c  # noqa: E731
    return sorted([p.get("quote"), s.get("evaluative_expression"), value(s.get("polarity")),
                   value(s.get("criterion")), value(s.get("creator"))]
                  for p in answer.get("passages", []) for s in p.get("statements", []))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--step", choices=("reviewer", "analyst"), default="reviewer")
    ap.add_argument("--articles", nargs="+", default=DEFAULT_ARTICLES)
    ap.add_argument("--repeats", type=int, default=3, help="requests per article and variant")
    args = ap.parse_args()

    cfg = load_config()
    step_cfg = cfg["annotation"][args.step]
    client = LLMClient.from_config(cfg)
    folder = output_folder(cfg, args.step, sample=True)
    out = folder.parent / "temperature-test"
    out.mkdir(exist_ok=True)
    path = out / f"{args.step}-{dt.datetime.now():%Y%m%d-%H%M%S}.json"
    results = {"step": args.step, "started": dt.datetime.now().isoformat(timespec="seconds"), "articles": {}}

    for aid in args.articles:
        record = load_record(folder, aid)
        if record is None or record["status"] != "accepted" or "parts" in record or record.get("sent") is False:
            sys.exit(f"{aid}: needs an accepted {args.step} record of an article sent whole")
        first = record["attempts"][0]
        prompt = load_prompt(args.step, first["prompt_version"])
        if prompt.sha256 != first["prompt_sha256"]:
            sys.exit(f"{aid}: the prompt files changed since this request was made; cannot resend it unchanged")
        messages = [{"role": "system", "content": prompt.system}] + first["messages_after_system"]
        settings = dict(first["settings"])
        variants = {"as configured": settings, f"with seed {SEED}": {**settings, "seed": SEED}}
        stored = {"raw": first["raw_response"], "content": content(args.step, first["raw_response"])}
        entry = results["articles"][aid] = {"stored": stored, "variants": {}}
        print(f"\n{aid} (stored answer from {first['answered_at']}, temperature {settings.get('temperature')})")
        for name, sets in variants.items():
            answers = []
            for i in range(args.repeats):
                started = dt.datetime.now()
                try:
                    reply = client.chat(first["model_requested"], messages, sets)
                except LLMError as e:
                    print(f"  {name} #{i + 1}: failed: {e}")
                    answers.append({"error": str(e)})
                    continue
                secs = (dt.datetime.now() - started).total_seconds()
                details = reply.usage.get("completion_tokens_details") or {}
                answers.append({"raw": reply.text, "reasoning": reply.reasoning, "usage": reply.usage,
                                "model_reported": reply.model, "seconds": round(secs),
                                "content": content(args.step, reply.text)})
                print(f"  {name} #{i + 1}: {secs:.0f} s, {details.get('reasoning_tokens')} reasoning tokens, "
                      f"{len(answers[-1]['content'] or [])} {'actions' if args.step == 'reviewer' else 'statements'}")
                entry["variants"][name] = answers
                path.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            ok = [a for a in answers if "raw" in a]
            same_text = len({a["raw"] for a in ok}) == 1
            same_reasoning = len({a["reasoning"] for a in ok}) == 1
            same_content = len({json.dumps(a["content"]) for a in ok}) == 1
            like_stored = sum(a["content"] == stored["content"] for a in ok)
            print(f"  {name}: {len(ok)} answers; identical text: {same_text}; identical reasoning: "
                  f"{same_reasoning}; same {'actions' if args.step == 'reviewer' else 'statements'}: "
                  f"{same_content}; same as the stored answer: {like_stored} of {len(ok)}")
            entry["variants"][name] = answers
            entry[f"summary {name}"] = {"answers": len(ok), "identical_text": same_text,
                                        "identical_reasoning": same_reasoning, "same_content": same_content,
                                        "same_as_stored": like_stored}
    results["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    path.write_text(json.dumps(results, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nanswers kept in {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
