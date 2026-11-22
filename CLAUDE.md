# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A pipeline that builds a dataset of **evaluative statements about creators and their works** from two 19th-century British periodicals (*The Monthly Repository*, 1806–1837; *The Leader*, 1850–1860) in the NCSE v2.0 OCR edition (CC BY 4.0, DOI 10.5522/04/28381610). An LLM **analyst** proposes annotations; a separate LLM **reviewer** may only delete them or lower their evidence level. It is also a teaching example for humanists, so documentation clarity matters as much as the code.

**Current state:** stages 1–3 (acquire, inspect, prepare) are implemented in Python; later stages are not. Record new technical choices in `docs/decisions.md`, keep the exact run commands for every stage in `README.md` ("Running the pipeline"), and keep the commands below up to date.

## Commands

- Setup: `uv sync` (uv manages Python and packages; D-009)
- Stages: `uv run ncse acquire`, `uv run ncse inspect`, `uv run ncse prepare`
- All tests: `uv run pytest`; one test: `uv run pytest tests/test_rebuild.py::test_page_break_is_noted`
- No linter is configured.

## Code layout

- `config.yaml`: all paths and settings. `src/ncse/cli.py`: the `ncse` command.
- `source.py` loads NCSE boxes, joins labels and marks invented text (`invented.py`, D-017); `rebuild.py` (pure functions, D-016) cuts issues into units at headings and turns them into articles; `inspection.py` and `prepare.py` are the stage scripts; `runlog.py` logs counts to `logs/`.
- NCSE facts that the code relies on: an entry is a layout box, not an article. Labels come from separate classification parquets, joined on `bbox_uid = page_id + "_" + box_page_id`. Topics are multi-label. Only the LDR (Leader) and MRP (Monthly Repository) issue series are used (D-010, D-011).

## Read first, every session

- `AGENTS.md`: binding working rules (git, documentation, reproducibility, LLM/code division, output checks, tests). Treat it as part of this file.
- `STATUS.md`: stage table and next steps. Update it at the end of every session.
- `docs/decisions.md`: decision log (append-only, IDs `D-xxx`; open questions `Q-1`…`Q-6`, of which Q-4 and Q-6 are answered). Don't decide an open question silently: record a provisional decision or ask.
- `docs/annotation-guidelines.md` (*what* to annotate) and `docs/evidence-and-review.md` (*how sure*, and the reviewer's limits). These define the schema the code must enforce.

## Approval gates (✋): stop and report to the project owner

1. After data inspection plus the prepared corpus: report what an NCSE entry is, how well the selection rule works, and a sample of article files with their metadata rows.
2. After drafting the analyst/reviewer prompts and the output format.
3. After the pilot run (20–30 articles from both periodicals).

Before the full run, give a request/token cost estimate. Never run full annotation before gates 1–3 are approved.

## Pipeline architecture

Stages are chained. Each reads the previous stage's output, runs with one command, is resumable (paid LLM calls are never redone), and logs counts of processed, skipped, failed and retried items plus requests and tokens:

1. **Acquire**: download NCSE v2.0 and record origin, date and checksum. Raw downloads are not committed.
2. **Inspect & select**: initial rule (D-002, provisional) is text type = *article* AND topic = *Arts, culture, entertainment and media*. Known caveats: the labels are LLM-assigned and unverified, NCSE entries may be fragments smaller than articles (so articles must be rebuilt), and the text has OCR errors.
3. **Prepare corpus** (D-007): one `.txt` per article (text only, no header, OCR unchanged, file name = article ID) plus `metadata.csv` (ID, file name, periodical, date/vol/no, pages, heading, length, NCSE labels, **the NCSE entry IDs it was built from**, rebuild notes) and `excluded_boxes.csv` (invented OCR text left out, with reasons; D-017). This corpus is the **only** input to all later stages, and quotations are matched against these files.
4. **Analyst** LLM → 5. **code checks** → 6. **Reviewer** LLM → 7. **code checks of reviewer diff** → 8. **Assemble** CSV + data dictionary → 9. **Descriptive statistics**.

There must also be a cheap **sample mode** that runs every stage on the corpus sample (`corpus_sample/`). Once the corpus is approved, it is published as a GitHub release and later stages fetch it (D-008); see README "Building the corpus or fetching the published one".

## Annotation model (what the validators enforce)

- **Unit** (D-003): one statement = one target × one criterion × one polarity. Each statement has its own ID and a shared passage ID.
- **Fields**: `quote`, `creator`, `art`, `work_title`, `work_genre`, `evaluative_expression`, `polarity`, `sarcastic`, `criterion`, `quoted_source`, plus evidence levels and assumptions. Final names are fixed in the data dictionary.
- **Controlled values**: art ∈ {literature, music, theatre, visual art, other}; polarity ∈ {positive, negative}; sarcastic ∈ {yes, no}; criterion ∈ {aesthetic value, moral value, usefulness, novelty, tradition}; evidence ∈ {observed, inferred, suggested}. Do not invent new categories or values.
- **Evidence** (D-004): a level per filled field. `inferred`/`suggested` require assumptions. The quote is always `observed`. The statement-level evidence is the lowest of its claims.
- **Quote fidelity**: the quote must be a verbatim substring of the article `.txt`, and `evaluative_expression` must occur inside the quote. Only documented trivial differences are tolerated (whitespace and line breaks; others are open question Q-5, record them in `decisions.md`).
- **Reviewer diff check** (D-005): the only allowed changes are deleting a claim/statement (marked `DELETED`, with a reason) and downgrading observed→inferred, inferred→suggested or observed→suggested (with a reason). Reject any added statement, changed value, rewritten text or raised level. Deleted statements stay in the final table.
- On a failed check: log it, retry a bounded number of times, then mark the item failed and report it. Never hand-fix an LLM output or drop an item silently.

## Key constraints

- LLM access goes through the university **LiteLLM** service (OpenAI-compatible). Credentials come from environment variables only.
- Prompts are separate, versioned files. Every annotation records the article, passage, model, settings, prompt version and run date. Raw LLM responses are kept.
- All configuration (paths, model names, sample sizes) lives in one config file.
- The LLM only does reading and judgement. Code does counting, formatting, matching and validation.
- Never edit data by hand. Apply corrections as code (e.g. a documented exclusion list).
- Write docs for humanists: explain terms the first time you use them and prefer plain words.
- Derived datasets must credit NCSE and Bourne's edition.
