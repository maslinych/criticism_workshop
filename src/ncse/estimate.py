"""Estimate the number of requests and tokens before a run (AGENTS.md, section 8).

`uv run ncse estimate` (or `--sample`) counts the characters of every analyst
request that would be sent and converts them to tokens with a rough rule of
4 characters per token for English text. The real count depends on the model's
tokenizer, so treat the result as an order of magnitude.

Output tokens cannot be known in advance. If analyst or reviewer answers are
already stored (for example from the pilot, in sample mode), the averages
measured there are used to extrapolate; otherwise only the input is estimated.
"""

import json

from . import parts
from .annotate import corpus_folder, load_articles, output_folder, read_text
from .prompts import load_prompt

CHARS_PER_TOKEN = 4


def measured(cfg: dict, step: str) -> dict | None:
    """Average real token counts per article from stored answers (sample or full)."""
    n = prompt = completion = requests = 0
    for mode in (True, False):
        folder = output_folder(cfg, step, mode)
        if not folder.is_dir():
            continue
        for path in folder.glob("*.json"):
            record = json.loads(path.read_text(encoding="utf-8"))
            if record["status"] != "accepted" or not record["attempts"]:
                continue
            n += 1
            requests += len(record["attempts"])
            for a in record["attempts"]:
                prompt += (a.get("usage") or {}).get("prompt_tokens", 0)
                completion += (a.get("usage") or {}).get("completion_tokens", 0)
    if not n:
        return None
    return {"articles": n, "requests": requests / n, "prompt": prompt / n, "completion": completion / n}


def run(cfg: dict, sample: bool = False) -> None:
    folder = corpus_folder(cfg, sample)
    articles = load_articles(folder)
    ann = cfg["annotation"]
    analyst = load_prompt("analyst", ann["analyst"]["prompt_version"])
    reviewer = load_prompt("reviewer", ann["reviewer"]["prompt_version"])
    texts = [read_text(folder, a) for a in articles]
    text_chars = sum(len(t) for t in texts)
    n = len(articles)
    # Long articles are sent in parts, each with some context (D-034).
    limit = ann.get("max_part_chars")
    opening, before = ann.get("context_opening_chars", 1500), ann.get("context_before_chars", 1500)
    spans = [parts.split(t, limit) if limit else [(0, len(t))] for t in texts]
    requests = sum(len(s) for s in spans)
    context_chars = sum(len(parts.context(t, start, opening, before)) for t, s in zip(texts, spans) for start, _ in s)
    # Each request carries the instructions, the user message frame and the article or part.
    frame = len(analyst.system) + len(analyst.user_template)
    analyst_in = (requests * frame + text_chars + context_chars) / CHARS_PER_TOKEN
    print(f"Corpus: {folder} — {n:,} articles, {text_chars:,} characters of text")
    if requests > n:
        print(f"Long articles in parts (max_part_chars {limit:,}): {sum(len(s) > 1 for s in spans):,} articles "
              f"in {sum(len(s) for s in spans if len(s) > 1):,} parts, with {context_chars / CHARS_PER_TOKEN:,.0f} "
              "tokens of context in all")
    print(f"Analyst, first attempts only: {requests:,} requests, about {analyst_in / 1e6:.2f} million input tokens "
          f"({frame / CHARS_PER_TOKEN:,.0f} of them per request are the instructions)")
    m = measured(cfg, "analyst")
    if m:
        print(f"Measured on {m['articles']} stored analyst answers: {m['requests']:.2f} requests, "
              f"{m['prompt']:,.0f} input and {m['completion']:,.0f} output tokens per article")
        print(f"  extrapolated: {n * m['requests']:,.0f} requests, {n * m['prompt'] / 1e6:.2f} M input, "
              f"{n * m['completion'] / 1e6:.2f} M output tokens")
    else:
        print("  output tokens: unknown until some answers are stored (run the pilot in sample mode first)")
    r = measured(cfg, "reviewer")
    rframe = (len(reviewer.system) + len(reviewer.user_template)) / CHARS_PER_TOKEN
    if r:
        print(f"Reviewer, measured on {r['articles']} stored answers: {r['requests']:.2f} requests, "
              f"{r['prompt']:,.0f} input and {r['completion']:,.0f} output tokens per article reviewed")
        print(f"  extrapolated (if every article had statements): {n * r['prompt'] / 1e6:.2f} M input, "
              f"{n * r['completion'] / 1e6:.2f} M output tokens")
    else:
        print(f"Reviewer: per article about {rframe:,.0f} tokens of instructions + the article + the "
              "analyst's statements; articles without statements are not sent")
