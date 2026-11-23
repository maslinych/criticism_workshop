# Decision log

This file records the decisions made in the project and why they were made. That includes general design choices and small rulings on particular annotation cases. Add new entries at the end and never delete old ones. If a decision is changed, add a new entry that refers to the old one.

**Entry format**

- **ID and title**
- **Date**
- **Status:** adopted / provisional / replaced by D-xxx
- **Decision:** what was decided
- **Reason:** why
- **Consequences:** what changes in the code, the prompts or the data

---

## Decisions taken in the project brief

**D-001 — Source and periodicals**
Status: adopted. The source is NCSE v2.0, and the periodicals are *The Monthly Repository* and *The Leader*. Reason: the edition is openly licensed (CC BY 4.0), split into units and labelled by topic, and these two periodicals carry the most literary and art criticism.

**D-002 — Initial selection rule**
Status: provisional until the data has been inspected. Select entries with text type *article* and topic *Arts, culture, entertainment and media*. Reason: this is the simplest rule using the existing labels. Its accuracy is checked in stage 2 (see `README.md`).

**D-003 — Unit of annotation: one statement = one target × one criterion × one polarity**
Status: adopted. Reason: this lets several judgements in one passage be counted separately while staying linked through a shared passage identifier.

**D-004 — Evidence levels are assigned per claim (field); the statement takes the lowest level**
Status: adopted, open to revision by the project owner. Reason: within one statement, different fields often rest on different kinds of evidence. For example, the title may be stated while the criterion is inferred. Per-field levels let the reviewer act precisely, and the statement-level summary keeps filtering simple.

**D-005 — The reviewer may only delete or downgrade, always with a reason; deleted items are kept and marked**
Status: adopted. Reason: see `evidence-and-review.md`, section 5. Requiring a reason for downgrades as well as deletions makes the review step open to inspection.

**D-006 — Source text is never corrected; quotations reproduce OCR errors**
Status: adopted. Reason: quotations are checked by code against the source text, and corrections would break traceability.

**D-007 — A readable prepared corpus as the fixed input to annotation**
Status: adopted. Data preparation writes one plain-text file per article, containing text only, plus a `metadata.csv` with one row per article, including the NCSE entry identifiers each article was built from. All later stages read only this corpus. Reason: people can read and check the corpus without special tools, quotations can be verified against simple text files, and the corpus can be shared or reused independently of the annotations.

**D-008 — The approved corpus is frozen and published as a GitHub release; later stages fetch it**
Status: adopted. The approved corpus is published as a versioned release asset (zip + SHA-256 checksum + `CORPUS_README.md`, tag `corpus-vX.Y`) on the project repository. Annotation work starts from the fetched release; building from NCSE (stages 1–3, about 900 MB of source data) remains possible and reproducible. A raw NCSE sample (test data for stages 2–3) and a 20–30-article corpus sample (for sample mode) are committed as plain files. Reasons:
- The source data is large, while the corpus is small.
- A release adds nothing to the git history and has a stable address.
- The tag ties the corpus to the code that built it.
- Annotations can always point to an exact, unchanging corpus version.
- Committing a zip to git would grow the history with every rebuild and bring no saving in space.

## Decisions taken while building the pipeline

**D-009 — Tools: Python with uv**
Date: 2026-11-22. Status: adopted.
Decision: the pipeline is written in Python (3.12 or later). Its packages are managed with *uv*, a tool that installs exactly the package versions recorded in `uv.lock`. Libraries: `polars` (reads the NCSE parquet files, a compact table format), `pyyaml` (reads `config.yaml`) and `pytest` (tests). Every stage is started with `uv run ncse <stage>`.
Reason: Python is the most common programming language in the digital humanities, and uv gives every user the same environment with one command.
Consequences: commands in `README.md` and `AGENTS.md`.

**D-010 — The Leader: town edition (LDR) only**
Date: 2026-11-22. Status: adopted (project owner).
Decision: use only issues whose NCSE identifier starts with `LDR`. Leave out the `CLD` series and the two `FLDR` issues.
Reason: NCSE holds two editions of *The Leader* for most dates, `LDR` and `CLD`. They print largely the same text, OCR'd separately, and 442 dates appear in both. Keeping both would count the same review twice. See `reports/01-data-inspection.md`.
Consequences: 543 issues are used. The 18 dates found only in `CLD` are lost.

**D-011 — The Monthly Repository: regular issues (MRP) only**
Date: 2026-11-22. Status: adopted (project owner).
Decision: use only issues whose NCSE identifier starts with `MRP`. Leave out supplements (`SMRP`), front matter and indexes (`FMRP`) and the single `EMRP` issue.
Reason: front matter repeats the contents of the regular issues and includes pages the OCR model invented. The supplements are few and contain almost no arts material (8 selected boxes).
Consequences: 285 issues are used.

**D-012 — Rebuilding articles from NCSE boxes**
Date: 2026-11-22. Status: replaced by D-016 (was provisional, chosen by the project owner from the options in the inspection report).
Decision: an NCSE entry is a *box* on a page, not an article. Articles are rebuilt issue by issue, with boxes taken in reading order (page, then reading order on the page):
1. The issue is cut into *segments* at title boxes. A run of consecutive title boxes is the heading of the segment that follows it.
2. Inside a segment, the text boxes that meet the selection rule (D-002) are found. Selected boxes with at most 2 unselected boxes between them (`rebuild.max_gap` in `config.yaml`) form one article, and the unselected boxes between them are included (*bridged*).
3. The segment heading is attached to the first article of the segment if that article starts within 2 boxes of it.
4. Every bridged box, page crossing and missing heading is recorded in `rebuild_notes` in `metadata.csv`.
Reason: the labels are assigned box by box and are noisy. One review often has an arts label on one box and other labels on the next. Title boxes are often missed in the *Monthly Repository*, so a segment there can run to 39 pages. Splitting at titles alone would therefore mix much unrelated text into the articles. Keeping only runs of selected boxes would leave many one-box fragments. The rule keeps nearly all labelled arts text, repairs short label gaps and never takes in a whole long segment.
Consequences: many articles are still fragments (1,763 of 3,901 Leader articles and 725 of 1,226 Monthly Repository articles consist of one text box). Some selected texts are not criticism, such as advertisements for books. Code: `src/ncse/rebuild.py`. Tests: `tests/test_rebuild.py`.

**D-013 — Figure and table boxes are left out of the corpus text**
Date: 2026-11-22. Status: provisional.
Decision: boxes of class `figure` and `table` are not put into article texts. When one falls inside an article, this is noted in `rebuild_notes`.
Reason: a `figure` box holds the OCR model's *description* of a picture ("The image depicts…"), not text printed in the periodical. A `table` box holds a table re-typed by the model with tabs and quotation marks, so quotations could not be matched against the printed layout.
Consequences: 195 articles carry a note about an omitted figure or table.

**D-014 — File layout, and a sample corpus kept in git**
Date: 2026-11-22. Status: adopted.
Decision: all settings are in `config.yaml`. Downloads go to `data/raw/` and the full corpus to `data/corpus/full/`; neither is committed to git, and both are rebuilt by the scripts. A sample corpus (12 articles per periodical, at least 1,500 characters each, fixed random seed; D-008 asks for 20–30) is written to `corpus_sample/` and committed, for sample mode and tests. The raw NCSE sample and the fetch stage required by D-008 belong to the next stage (see `STATUS.md`). Generated reports go to `reports/`.
Reason: the downloads are about 1 GB. The sample lets the later stages be tried and tested quickly without the full data.

**D-015 — Article identifiers and metadata columns**
Date: 2026-11-22. Status: adopted.
Decision: article ID = periodical code + issue date + running number of the article in the issue, for example `LDR-1852-12-11-003`. The text file is named `<article ID>.txt`. The columns of `metadata.csv` are described in `corpus_sample/README.md` and in `src/ncse/prepare.py`. Volume and issue number are not included: NCSE v2.0 does not provide them as data. They appear only inside the OCR text, so extracting them would be guesswork.
Reason: the identifier can be read by a person, sorts by date, and stays the same as long as the data and the rebuild rule are unchanged.
Consequences: if the rebuild rule changes, running numbers may change. The `ncse_entry_ids` column is the lasting link to NCSE.

**D-016 — Rebuilding articles: whole units between headings (replaces D-012)**
Date: 2026-11-22. Status: adopted for the pilot (approved by the project owner at ✋1, 2026-11-22); review after the pilot.
Decision: the project owner asked for fragments to be completed into whole articles where possible, rather than dropped. False positives (selected texts that are not criticism) are acceptable as long as they do not dominate the corpus. Articles are now rebuilt issue by issue, with boxes in reading order:
1. The issue is cut into *units* at headings. A heading is a title box, or a text box that *begins* with a heading. Three kinds are recognised: a phrase in capitals ending in a full stop ("HEINE'S POEMS."), a numbered review ("Art. VI.—"), or a book heading (a capital letter, then "By"/"Edited by" plus a name and a mark of publication such as "8vo.", "pp.", "2 vols." or "London:", all within the first 250 characters). Running page headers ("THE LEADER. [No. 438 …") are not headings.
2. A unit with at least one box meeting the selection rule (D-002) is taken **whole** if it spans at most 3 pages (`rebuild.max_pages`) and either its first text box carries the arts topic label, whatever its text type except *advert*, or at least half of its characters lie in selected boxes (`rebuild.whole_share`).
3. Otherwise only the selected part of the unit is taken, exactly as under D-012 (gaps of up to 2 boxes bridged, title attached if close).
4. Figure and table boxes (D-013) and invented text (D-017) never go into an article. `metadata.csv` gains a column `whole_unit` (yes/no), and `rebuild_notes` records how each article was built, including the kind of heading it starts at.
Reason: in *The Leader* review titles are often not title boxes but the first words of a text box ("REED ON ENGLISH LITERATURE. English Literature from Chaucer to Tennyson. By Henry Reed."), so one title segment held several reviews. Within a review the labels change from box to box, and many review boxes are typed "poem/song/story" or "other" rather than "article". A review whose first box carries the arts label is therefore taken in full even when later boxes carry other labels. In the samples read, these whole units were complete reviews that D-012 had cut into fragments, for example of Wilkie Collins's *The Queen of Hearts*, Eugène Sue's *Les Enfants de l'amour*, Plato's *Republic* and the Mirabeau–La Marck correspondence. The 3-page limit stops a missed heading from pulling in a long stretch of unrelated text.
Consequences (numbers after excluding invented text): *The Leader* 4,135 articles and 3.37 million words, of which 3,059 are whole units (D-012: 3,901 articles, 3.05 million words). *The Monthly Repository* 1,240 articles and 0.52 million words, of which 397 are whole units (D-012: 1,226 articles, 0.49 million words). Articles that start without any heading fell from about 1,350 to 892 in *The Leader*. The *Monthly Repository* gains less: its layout misses many headings, and 417 units there run over more than 3 pages, so most of its articles are still selected parts. Known weaknesses: when the next heading is missed, a whole unit can run on into an unrelated item (e.g. a review ending with a news paragraph); lists of new books can open with a book heading and are then taken whole. Code: `src/ncse/rebuild.py`; tests: `tests/test_rebuild.py`. The article identifiers of D-012 are not kept (D-015).

**D-017 — Text invented by the OCR model is left out and listed (answers Q-6)**
Date: 2026-11-22. Status: adopted (project owner: exclude invented text and record what was excluded, with the reason).
Decision: a text or title box counts as invented, and is left out of all articles, when either
1. **output limit:** the OCR model wrote 2,000 tokens for every part of the box (`completion_tokens` ≥ 2,000 × `segment_count`). In *The Leader*, 4,403 boxes have exactly 2,000 tokens, far more than any other value, so this is the model's output limit: the model was cut off while still writing; or
2. **loop:** at least 30% of the box's 8-word sequences occur more than once in the same box (only words containing a letter are counted, so dot leaders and number lists do not count).
Every excluded box that lies inside an article, or that meets the selection rule and would have formed an article, is listed in `excluded_boxes.csv` next to `metadata.csv`, with the reason, its length and the article it belongs to. The article's `rebuild_notes` also names it. In addition, `rebuild_notes` *flags* (without excluding) any box that mentions a year more than one year after the issue date.
Reason: boxes that reached the limit or repeat themselves were read in samples, and all were invented or corrupted, e.g. "The poem is a very different kind of poem from …" repeated to the end, a list of paintings including Alma-Tadema in 1853, or *Punch* discussed in an 1825 issue. On the boxes in the corpus the repeated share falls into two clear groups: real text stays below 0.3 (lists of names reach about 0.2), and loops lie above it. Remarks addressed to the user ("Certainly! Below is the extracted table") occur only in table and figure boxes, which are left out anyway (D-013). Years later than the issue date are only flagged, because most are OCR misreadings of a digit (1881 for 1851, 1869 for 1859).
Consequences: 1,152 (MRP) and 4,810 (LDR) boxes in the issues used count as invented, about 8% and 15% of their characters. 527 of them are listed in `excluded_boxes.csv` (3.3 million characters, about 0.55 million words, no longer sent to the LLM). Short invented passages without loops are **not** caught, for example a 325-character note in an 1851 issue about Trelawny's life of Byron (published 1858), or news of the death of King Theodore of Abyssinia (died 1868) in an 1857 issue. Neither mentions a year, so the year flag does not catch them either. The analyst may annotate such passages. They should be watched for in the pilot. Code: `src/ncse/invented.py`; tests: `tests/test_invented.py`; thresholds in `config.yaml` (`invented`).

**D-018 — The selection rule is not widened (answers Q-4)**
Date: 2026-11-22. Status: adopted (approved at ✋1, 2026-11-22; project owner's preference: fiction matters more than political or religious writing, and the corpus should not be inflated; widening is acceptable only if it can be done cleanly).
Decision: no texts are added beyond D-002 and the whole-unit rule of D-016.
Reason: a clean rule was tested: take any unit that opens with a book heading (D-016) but has no selected box. It would add about 244,000 words to the *Monthly Repository* (+47%), almost all reviews of sermons, theological tracts and letters (topic *religion* in 449 of 534 units), and about 212,000 words to *The Leader* (+6%), mostly history, travel, science and politics, plus some news paragraphs caught by mistake. Few of the added texts are reviews of fiction; fiction reviews mostly carry the arts label already. The whole-unit rule of D-016 already recovers the rest of a review whose labels change from box to box. The Leader's literature section, found by its motto ("Critics are not the legislators…", 368 boxes in 366 issues), is mostly already selected (237 of the 368 motto boxes).
Consequences: reviews of religious and political books whose opening box lacks the arts label stay out of the corpus.

**D-019 — Packaging, publishing and fetching the corpus**
Date: 2026-11-22. Status: adopted.
Decision: the corpus was approved at ✋1 on 2026-11-22. It is published as described in D-008, with these details:
- `uv run ncse prepare` writes `BUILD.json` next to `metadata.csv`, recording the git commit of the code that built the corpus and whether there were uncommitted changes.
- `uv run ncse package` writes `dist/ncse-arts-corpus-v<version>.zip`, a `.sha256` file in the format `sha256sum -c` reads, and `CORPUS_README.md`. The README is generated from `config.yaml` and the corpus itself (attribution, licence, counts, method, column descriptions, commit). The zip holds one folder `ncse-arts-corpus-v<version>/` with `texts/`, `metadata.csv`, `excluded_boxes.csv`, `BUILD.json` and `CORPUS_README.md`. Every file in the zip carries the same fixed date, so packaging the same corpus twice gives the same checksum. `package` refuses to run if there are uncommitted changes, or if the corpus was built at a commit other than the current one.
- Publishing is done by the project owner by hand: tag `corpus-v<version>` on the commit in `BUILD.json`, push, create the GitHub release and upload the two files (commands in `README.md`, "Publishing the corpus"). The pipeline never publishes anything itself.
- `uv run ncse fetch` downloads the zip and checks its SHA-256 checksum. It checks against `release.sha256` in `config.yaml`; until that is filled in after publishing, it checks against the published `.sha256` file. It refuses zips with paths outside their folder, unpacks into `data/corpus/full/` and writes `FETCHED.json`. It does not overwrite an existing corpus unless given `--force`.
Reason: the tag must point to the code that built the corpus, and the checksum must be checked against a value that cannot change with the download. Publishing is an outward-facing act that cannot be undone (D-008: releases are never replaced), so it stays with the project owner.
Consequences: the version is set in `config.yaml` (`release.version`). A new corpus version means changing it and packaging again. Tests: `tests/test_release.py` packages the sample corpus and fetches it back without network access.

**D-020 — The main branch is agent-neutral**
Date: 2026-11-22. Status: adopted (project owner).
Decision: the `main` branch carries no files for a particular coding agent. All rules and orientation for agents and contributors are in `AGENTS.md`, which many coding agents read, and which now also has a map of the commands, code and data (section 10). Development continues on a separate branch, which may hold agent-specific files (such as `CLAUDE.md`) that are kept out of `main` when changes are merged into it.
Reason: anyone who clones the repository can use any coding agent, or none.
Consequences: `CLAUDE.md` was removed from `main` and its general content moved to `AGENTS.md`.

**D-021 — The raw NCSE sample**
Date: 2026-11-22. Status: adopted.
Decision: `uv run ncse sample-raw` writes `raw_sample/`, committed to git. It holds the original NCSE rows (boxes plus their two label rows) for every box on the pages of 12 articles, 6 per periodical. Per periodical, 3 articles are taken as whole units, 2 as selected parts and 1 has a box of invented text left out. They are drawn at random (seed in `config.yaml`, `raw_sample`) among articles whose unit spans at most 2 pages. All boxes on the pages of each article's unit are copied, so the article comes out of the sample exactly as out of the full data. The files keep the folder layout of the download but are plain CSV instead of parquet. `source.py` reads either format, so the real code runs on the sample when `paths.raw` points to it. `articles.csv` records, for each chosen article, its NCSE boxes, notes and a checksum of its text. The script checks the sample against this file before writing it, and so does `tests/test_raw_sample.py`.
Reason: D-008 asks for a raw sample that lets stages 2–3 be tested and understood without the 1 GB download. CSV can be read without special tools and keeps the OCR text exactly (tested on line breaks, quotation marks and empty texts). Copying whole pages, not just the article's boxes, keeps the context the rebuild rule depends on: headings, neighbouring boxes and unit length.
Consequences: 172 boxes on 18 pages, about 320 KB. Articles other than the chosen 12 that appear on the same pages may be cut off at the edge of the copied pages.

## Decisions from a test round of the annotation stages

A trial version of the analyst and reviewer steps was run against the LiteLLM service with several models, on articles of the corpus sample. The practical lessons are in `docs/llm-service.md`; these decisions follow from them and bind the implementation of stages 4–7.

**D-022 — Quotation matching in three levels (answers Q-5)**
Date: 2026-11-22. Status: adopted (project owner).
Decision: a quotation is matched against the article's text file, and an evaluative expression against the text of its quotation, at the strictest of three levels that succeeds. The level is recorded with every passage and statement.
- *Exact*: the same characters; only whitespace may differ (any run of spaces, tabs and line breaks counts as one space; spaces at the start and end are ignored).
- *Normalised*: the same letters and digits in the same order, ignoring every other character and capital letters. This accepts differences in punctuation, the form of quotation marks and dashes, line breaks, words broken by a hyphen at a line end, and capitals, as long as the words stay the same. Accepted without a flag.
- *Approximate*: as *normalised*, but a few letters or digits may differ (inserted, left out or replaced), as when the model silently corrects an OCR error or makes a typo. Accepted with a flag. The allowance depends on length: at most 3 characters, and at most 5% of the letters and digits of the quoted text, so phrases under 20 letters get none. Both numbers are settings in the configuration file.

A normalised or approximate match must begin and end at word boundaries in the text, so that a changed letter cannot turn "any ground" into "no ground". Whatever the level, the code records where the match lies in the text file and the exact text found there; **the dataset uses that source text, never the model's copy**, so traceability (README) and D-006 hold. The tolerance used is stored with the results, so that re-checking later gives the same outcome. The prompt still asks the model to copy exactly; the tolerance is not mentioned to it.
Reason: in the test round, quotations failed almost only where the model tidied the text at a break in the corpus. It dropped a stray full stop between two text boxes, joined a hyphen-broken word, or left out a semicolon inside quotation marks; none of these changes a word. Rejecting them lost good statements. The word-boundary rule was added after a test showed that "no ground for supposing" would otherwise match "any ground for supposing" with one changed letter.
Consequences: `AGENTS.md`, section 6, describes the rule. The quotation matcher needs tests for each level and for the word-boundary rule.

**D-023 — Checking LLM answers: rejected answers and set-aside items**
Date: 2026-11-22. Status: adopted (project owner).
Decision:
- Only a problem with the analyst's answer **as a whole** rejects it and leads to a retry: it is empty, is not a bare JSON object, is not valid JSON, does not match the agreed structure, or was cut off at the length limit.
- A **passage** whose quotation is not found is set aside together with its statements. A **statement** that breaks a rule (its evaluative expression is not in its quotation, it has no target, an evidence rule is broken, a value is badly formed) is set aside alone. Set-aside items are kept with their reasons and with what the model wrote, counted in the log and listed in the stage report, but they do not enter the dataset. They are not retried. Items keep their numbers, so that passage 4 stays passage 4 when passage 3 is set aside, and everything can be traced back to the raw answer.
- If the model returns exactly the same answer as in the previous attempt, no further attempt is made and the article is marked failed with that reason.
- When an answer was cut off at the length limit, the retry sends back only its beginning (a couple of thousand characters), not the whole answer.
- The reviewer's answer is still accepted or rejected as a whole (D-005): any action outside its limits rejects it. The reviewer sees only accepted statements.
Reason: in the test round, a good answer of 30 statements was rejected entirely because 2 failed a check, and the retry cost a full answer. Asked to correct listed problems, one model returned the identical answer twice. A model caught in a loop wrote 70,000 characters; sending them back with the retry quadrupled the next request, and the model looped again. `AGENTS.md`, section 6, still holds: no failure is fixed by hand or dropped silently.
Consequences: `AGENTS.md`, section 6, describes the procedure.

**D-024 — Requests to the LLM service**
Date: 2026-11-22. Status: adopted (project owner).
Decision:
- **JSON through the interface.** Requests ask for JSON with the interface setting `response_format: {"type": "json_object"}`, in addition to the instruction in the prompt and the checks in code. It can be switched off in the configuration for a model that refuses it.
- **Settings in the configuration**, per step: model, `temperature` (0), a generous `max_tokens` (32,000 in the tests; reasoning counts against it), `reasoning_effort`, and a place for further model-specific options passed on unchanged. All settings sent are recorded with every answer.
- **Reasoning stays on** for reasoning models unless a test shows that turning it down keeps recall (`docs/llm-service.md`, section 1). The reasoning-token count is logged, and the reasoning text is stored with the answer if the service returns it.
- **Errors.** Quick "busy" answers (HTTP 429, 5xx) are retried after a growing pause and do not count as attempts. A gateway error (HTTP 502 or 504) or time-out that comes after a long wait (about 2 minutes, a setting) is not retried: that article is marked failed with the reason and the run goes on; several such failures in a row stop the run. Other refusals (wrong key, no access, unknown model) stop the run at once with a message saying what to check.
- **Stopping.** Ctrl-C sends no new request and ends any pause at once; answers already being paid for are saved if possible, and a second Ctrl-C quits at once. Every answer is saved as soon as it arrives, before it is checked.
Reason: see `docs/llm-service.md`. In short: without the JSON setting, models wrote text before the JSON; an output limit of 8,000 tokens was too small for both answer and reasoning; turning reasoning off cost recall; the service gives up on an answer after about 300 seconds, and retrying such requests wasted half an hour; Ctrl-C did not stop a run whose requests ran in the background.
Consequences: the model choice itself is left to the smoke test and the pilot; `docs/llm-service.md` says what to look for.

**D-025 — Variation between runs is estimated, not eliminated**
Date: 2026-11-23. Status: adopted as a principle (project owner); how to estimate it is still to be designed and tested.
Decision:
- **Answers vary between runs.** The same request, sent again unchanged, gives a different answer. On a shared LLM service this happens even with `temperature: 0` and a fixed `seed`, so repeatable answers cannot be assumed. Both steps vary: the analyst in which statements it finds and in the values it gives them, the reviewer in which statements it deletes or downgrades.
- **The variation is treated as a property of the method, not as a defect to remove.** It resembles the variation between human annotators who read the same text: clear cases come out the same almost every time, borderline cases do not. The methodologically sound response is to **measure** it and report it with the data, not to hide it behind a single run.
- **Uncertainty propagates through both steps.** The reviewer's variation adds to the analyst's, so an estimate must cover both: several analyst runs on the same articles, and several reviewer runs on each analyst run. A single run of each step is one draw from the possible results.
- **What the design must allow,** even before such runs are made:
  - several independent runs of a step on the same article, kept side by side, each identified by its run, never overwriting one another;
  - the reviewer run on a given analyst run, recorded as such;
  - a rule, carried out by code, for recognising the same statement in different analyst runs (identifiers differ between runs, and so does the exact wording the model picks out; the position of the quotation and the evaluative expression in the text is a natural basis);
  - statistics that can report, besides counts and shares, their spread across runs, and for each statement or reviewer action how many runs agree on it.
- **Combining runs** (for example keeping only what most runs agree on) is a possible later choice, but the data of every run must stay available, so that the agreement itself can be studied.
- **Comparing prompt versions or models.** A difference between two single runs is not evidence that a change worked: it may be run-to-run variation. Judge a change against the variation of repeated runs.
Reason: repeated requests in the pilot phase never gave identical answers. Plain evaluations were found by almost every run; milder and indirect ones, the choice of criterion, and the reviewer's decisions on borderline statements varied from run to run.
Consequences: `docs/evidence-and-review.md` (section 8) and `AGENTS.md` (sections 4 and 7) state the principle; `docs/llm-service.md` corrects the advice on `temperature`. A first full run may be a single run of each step, documented as such; the estimate of variation is planned as a separate step.

## Open questions for the project owner

These should be settled during or after the pilot, then recorded as decisions.

- **Q-1. Performers.** Do evaluations of actors, singers and musicians count as evaluations of "creators"?
- **Q-2. Other targets.** How are evaluations of exhibitions, theatres, concerts as events, editions and translations treated?
- **Q-3. The `other` category for art.** Opera could count as music or theatre, and book illustration as literature or visual art. Which rules apply to such boundary cases, and does `other` stay as a category?
- **Q-4. Selection beyond the topic label.** *(Answered: D-018.)* Should texts labelled with other topics (e.g. *Religion*, *Education*) that contain reviews be added? If so, how are they identified?
- **Q-5. Quotation matching tolerances.** *(Answered: D-022.)* Which trivial differences may the quotation check ignore, beyond whitespace and line breaks?
- **Q-6. Text the OCR model invented.** *(Answered: D-017.)* NCSE v2.0 was read by an image-to-text model, which sometimes adds text that is not on the page: invented newspaper headers (for example "TUESDAY, AUGUST 20, 1861" on an 1851 page), sentences repeated in a loop, and remarks addressed to the user ("Certainly! Below is the extracted table…"). Should such passages be detected and excluded, flagged in the metadata, or left alone? For now they are left in the text unchanged (D-006).

**Notes on Q-4 from the data inspection (2026-11-22).** The Leader opens its literature section with the motto "Critics are not the legislators, but the judges and police of literature". Boxes with this motto are sometimes labelled *education* or *religion* rather than arts. *Monthly Repository* reviews of theological books ("Art. III.—Religious Liberty Stated and Enforced… By Thomas Williams") are labelled *religion*. Section headings and review formulas ("Art. N.—", "By … pp.") could find such reviews. See `reports/01-data-inspection.md`.
