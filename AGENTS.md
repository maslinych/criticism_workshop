# Working rules

These rules apply to whoever builds this project, whether a coding agent or a person. Read them together with `README.md`, which states the goal. The annotation itself is defined in `docs/annotation-guidelines.md` and `docs/evidence-and-review.md`.

Technical choices (languages, libraries, file layout, internal formats) are yours to make, as long as they satisfy the rules below. Record significant choices in `docs/decisions.md`.

## 1. Before you start, and when you return

- Read `README.md`, this file, `STATUS.md` and `docs/decisions.md`.
- Respect the approval points (✋) listed in `README.md`. Do not run the full annotation before the prompts, the output format and the pilot results have been approved by the project owner.
- When something in the documents is unclear or contradictory, do not guess silently. Note the problem in `STATUS.md` and ask, or choose a provisional solution and record it in `docs/decisions.md` as provisional.

## 2. Version control

- Keep the project under **git**. Commit in small, meaningful steps with clear messages.
- Never commit credentials: API keys, passwords, tokens.
- Do not commit large downloaded source files. The download script and the recorded checksums make them reproducible.
- Do not commit the full prepared corpus. Publish it as a versioned GitHub release, as described in `README.md` ("Publishing the corpus"). Only the two small samples (raw NCSE sample and corpus sample) are committed, as plain files. Never commit zip archives of data.
- Never replace or modify a published corpus release. Corrections become a new version.
- Keep both ways of obtaining the corpus working: building it from NCSE and fetching the published release. A change to stages 1–3 that would change the corpus means a new corpus version.
- Prompts are part of the code: keep them as separate, versioned files, not hidden inside scripts.

## 3. Documentation: write everything down

- **`STATUS.md`** lists current tasks, how far along each one is, and anything important learned along the way. Update it at the end of every work session.
- **`docs/decisions.md`** records decisions with their reasons. This includes small decisions about how a particular kind of annotation case is handled (e.g. "a review of an opera counts as music, not theatre").
- **`README.md`** must always contain the exact commands for running every stage of the pipeline, from download to statistics.
- Write for readers who are humanists rather than programmers. Explain terms when you first use them, and prefer plain words to jargon.

## 4. Reproducibility

- **Everything in code.** Every step of collecting, selecting, annotating and assembling data is done by a script. Never edit data by hand. If a correction is needed, write it as code (e.g. a documented list of exclusions applied by a script).
- **One command per stage.** Each pipeline stage can be run on its own with a single documented command.
- **Configuration in one place.** Paths, model names, sample sizes and similar settings live in a configuration file, not scattered through the code.
- **Resumable.** If a run stops halfway, through a crash, a network error or a quota limit, running it again continues where it stopped. Finished work, and above all paid LLM calls, is never redone unless explicitly requested.
- **Provenance.** It must always be possible to trace where every piece of data came from:
  - source files: origin, download date and checksum;
  - every article in the prepared corpus: its source file and the identifiers of the NCSE entries it was built from, recorded in `metadata.csv`;
  - every annotation: the corpus version, the article, the exact passage, the model, the model settings, the prompt version and the date of the run;
  - the raw LLM responses: kept, so that any processed result can be checked against what the model actually returned.

## 5. What the LLM does and what code does

Divide the work strictly.

**Code does everything that can be described as a fixed procedure**, for example:

- downloading and filtering;
- splitting texts and assigning identifiers;
- checking formats and allowed values;
- matching quotations against the source;
- merging, counting and building tables and statistics.

**The LLM does only what needs reading and understanding**, for example:

- recognising an evaluation;
- interpreting what it refers to;
- judging irony;
- deciding which criterion applies;
- reviewing such judgements.

Never ask the LLM to count, sort, convert formats or check its own output format. Code does that, more cheaply and reliably.

## 6. Checking every LLM output

Every response from the LLM is checked by code before it is accepted.

- **Format.** The response has the agreed structure, all required fields are present, and controlled fields use only the allowed values.
- **Fidelity to the source.** Every quotation must match a passage of the source text, meaning the article's text file in the prepared corpus. Paraphrases and text that does not exist in the source are rejected. The evaluative word or phrase must occur inside its quotation.
  - The matching may ignore only trivial differences that leave the words unchanged: whitespace, line breaks, punctuation, the form of quotation marks, hyphenation and capitals. A few changed characters (a corrected OCR error, a typo) are accepted but flagged. These tolerances are written down in `docs/decisions.md` (D-028).
  - The dataset always uses the exact source text that a quotation matched, never the model's copy. The source texts are never corrected.
- **Consistency with evidence levels.** A value marked as *observed* (directly stated) should be findable in the text. If it is not, the statement is flagged.
- **Reviewer limits.** The reviewer's output is compared with the analyst's. Any change other than an allowed deletion or downgrade is rejected (see `docs/evidence-and-review.md`).

**When a check fails:**

1. Log the failure.
2. If the response as a whole is unusable (wrong format), retry the request a limited number of times. A passage or statement that fails a check is set aside as a failed item, and the rest of the response is accepted (D-027).
3. If the response still fails, mark the article as failed and report it. Report failed items too.

Never fix an LLM output by hand. Never drop a failed item silently.

## 7. Quality assurance

- **Automated tests:**
  - for the scripts, e.g. the quotation matcher;
  - for the integrity of the generated data: unique identifiers, exactly one text file for every row of `metadata.csv` and the reverse, every statement linked to an existing article, only allowed values in controlled fields, no empty required fields.
- **Logging.** Every run writes a log of what it did: items processed, skipped, failed and retried, plus the number of requests and tokens used.
- **Statistics after each stage.** Report how many texts were selected, how many statements were produced, how many failed checks, and how many were deleted or downgraded by the reviewer. Unexpected numbers are often the first sign of a problem.

## 8. Cost and access

- Credentials for the LiteLLM service come from environment variables.
- Estimate the number of requests and tokens before any large run, and report the estimate to the project owner.
- Respect rate limits. A failed or interrupted run should not lose money or work.

## 9. Things not to do

- Do not correct, modernise or normalise the source texts.
- Do not invent new annotation categories or values. If the existing ones do not fit, record the case and raise it with the project owner.
- Do not change the selection rule, the annotation guidelines or approved prompts without recording the change, and getting approval where required.
- Do not let the reviewer step add or rewrite annotations.
- Do not edit generated data by hand.

## 10. Orientation: commands, code and data

A quick map of the project for coding agents and new contributors. The rules above take precedence.

**Current state.** Stages 1–4 are done: the corpus is built and published as release `corpus-v1.0`, `uv run ncse fetch` downloads it, and `raw_sample/` lets stages 2–3 run and be tested without the download. Prompts and output format are approved (✋2). The annotation stages 4–7 are built and have run on the pilot sample twice; stages 8–9 (dataset and statistics) are built and tried on the two pilots. `STATUS.md` lists the next steps.

**Commands**

- Setup: `uv sync` (uv installs Python and the exact package versions in `uv.lock`; D-009).
- Get the corpus: `uv run ncse fetch` (published release), or build it from NCSE with `uv run ncse acquire`, `uv run ncse inspect`, `uv run ncse prepare`.
- Refresh the raw NCSE sample (`raw_sample/`, test data for stages 2–3): `uv run ncse sample-raw` (needs the download).
- Package a new corpus version: `uv run ncse package` (zip in `dist/`). Publishing (tag, push, GitHub release) is done by the project owner by hand; an agent never publishes (D-019).
- Annotation: `uv run ncse estimate`, `uv run ncse analyse`, `uv run ncse check analyst`, `uv run ncse review`, `uv run ncse check reviewer`; add `--sample` for sample mode. Needs `LITELLM_BASE_URL` and `LITELLM_API_KEY` and model names in `config.yaml`.
- Dataset and statistics: `uv run ncse assemble`, `uv run ncse stats` (`--sample` for sample mode; `assemble --annotation DIR --out DIR` and `stats --datasets DIR DIR …` to compare runs). No LLM requests.
- Tests: `uv run pytest`; one test: `uv run pytest tests/test_rebuild.py::test_page_break_is_noted`. No linter is configured.

**Code layout** (`src/ncse/`)

- `config.yaml` (project root): all paths and settings. `cli.py`: the `ncse` command.
- `source.py` loads NCSE boxes, joins their labels and marks text invented by the OCR model (`invented.py`, D-017).
- `rebuild.py` (pure functions, D-016) cuts issues into units at headings and turns them into articles.
- `prompts/<step>/v<N>/` (project root): prompt texts and the JSON schema of each answer (D-022); the format is specified in `docs/output-format.md`.
- `checks.py` (pure functions) checks both LLM steps' answers; `quotes.py` matches quotations; `annotate.py` runs the analyst and reviewer (records in `data/annotation/`, resumable); `parts.py` splits long articles into parts and joins the results (D-034); `checkreport.py` re-checks stored answers and writes reports; `llm.py` is the LiteLLM client; `prompts.py` loads prompt versions; `estimate.py` estimates cost.
- `inspection.py` and `prepare.py` are stages 2 and 3; `rawsample.py` draws the raw NCSE sample; `release.py` (package) and `fetch.py` handle the corpus release; `runlog.py` writes run logs with counts to `logs/`. `dataset.py` (stage 8) assembles the CSV tables and the data dictionary (`docs/data-dictionary.md`) into `data/dataset/<mode>/`; `stats.py` (stage 9) writes the descriptive statistics, comparing runs when given several datasets.

**NCSE facts the code relies on**

- An NCSE entry is a layout box on a page, not an article.
- The labels come from separate classification files, joined on `bbox_uid = page_id + "_" + box_page_id`. Topics are multi-label.
- Only the LDR (*Leader*) and MRP (*Monthly Repository*) issue series are used (D-010, D-011).

**Approval points (✋).** Stop and report to the project owner:

1. after the prepared corpus (approved 2026-11-22);
2. after drafting the analyst and reviewer prompts and the output format;
3. after the pilot run (20–30 articles from both periodicals).

Give a request and token cost estimate before the full run.

**Pipeline from here.** 4. analyst LLM → 5. code checks → 6. reviewer LLM → 7. code checks of the reviewer's changes → 8. assemble the CSV and data dictionary → 9. descriptive statistics.

- Each stage reads the previous stage's output, runs with one command and is resumable: paid LLM calls are never redone.
- Each stage logs the items processed, skipped, failed and retried, and the requests and tokens used.
- A cheap *sample mode* runs every stage on `corpus_sample/`.
- The prepared corpus is the only input; quotations are matched against its text files.

**What the validators must enforce** (from `docs/annotation-guidelines.md` and `docs/evidence-and-review.md`)

- **Unit** (D-003): one statement = one target × one criterion × one polarity. Each statement has its own identifier and a shared passage identifier.
- **Fields:** `quote`, `creator`, `art`, `work_title`, `work_genre`, `evaluative_expression`, `polarity`, `sarcastic`, `criterion`, `quoted_source`, plus evidence levels and assumptions. The final names are fixed in the data dictionary.
- **Controlled values:** art ∈ {literature, music, theatre, visual art, other}; polarity ∈ {positive, negative}; sarcastic ∈ {yes, no}; criterion ∈ {aesthetic value, moral value, usefulness, novelty, tradition}; evidence ∈ {observed, inferred, suggested}.
- **Evidence** (D-004): each filled field has a level. *Inferred* and *suggested* need assumptions; the quote is always *observed*. A statement's level is the lowest of its fields.
- **Quotations:** a quote matches a passage of the article's text file, and `evaluative_expression` occurs inside it. Matching is exact, normalised (punctuation, quotation marks, line breaks, hyphenation, capitals ignored) or approximate (a few changed characters, flagged); the exact source text is recorded (D-028). A failed passage or statement is set aside, not the whole answer (D-027).
- **Reviewer changes** (D-005): only deleting a field or statement (marked `DELETED`, with a reason) and downgrading a level (observed→inferred, inferred→suggested, observed→suggested, with a reason). Any added statement, changed value, rewritten text or raised level is rejected. Deleted statements stay in the final table.
