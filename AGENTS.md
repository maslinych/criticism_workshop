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
- **Fidelity to the source.** Every quotation is a verbatim passage of the source text, meaning the article's text file in the prepared corpus. Paraphrases, "tidied" quotations, corrected OCR errors and text that does not exist in the source are rejected. The evaluative word or phrase must occur inside its quotation.
  - The matching may ignore only trivial differences such as whitespace and line breaks. These tolerances must be written down in `docs/decisions.md`.
- **Consistency with evidence levels.** A value marked as *observed* (directly stated) should be findable in the text. If it is not, the statement is flagged.
- **Reviewer limits.** The reviewer's output is compared with the analyst's. Any change other than an allowed deletion or downgrade is rejected (see `docs/evidence-and-review.md`).

**When a check fails:**

1. Log the failure.
2. Retry the request a limited number of times.
3. If it still fails, mark the item as failed and report it.

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
