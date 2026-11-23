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

**D-022 — Format of the LLM answers, and prompt files**
Date: 2026-11-22. Status: adopted (approved at ✋2, 2026-11-22); the matching tolerance is replaced by D-028, and acceptance as a whole by D-027.
Decision:
- Both LLM steps answer in JSON. Each prompt version is a folder `prompts/<step>/v<N>/` with the instructions (`system.md`), the per-article message (`user.md`) and a JSON schema of the answer (`output.schema.json`). A version is frozen once used in a paid run; changes become a new version. The versions in use are set in `config.yaml` (`annotation`).
- One request per article; articles are not split. The longest article has about 6,100 words.
- The analyst returns a list of passages, each with a verbatim quote and the statements resting on it. Each claim field is `{value, evidence, assumption}`; an empty field is `null`.
- The reviewer returns only a list of actions (statement, field, delete or downgrade, new level, reason). It never repeats the statements, so it cannot rewrite or add anything.
- Identifiers, quotation positions and statement levels are computed by code (`p01-s02` in LLM messages; `<article ID>-p01-s02` in the data).
- Quotation matching tolerance: runs of whitespace (spaces, tabs, line breaks) count as one space, and leading and trailing whitespace is ignored. Nothing else is tolerated for now (Q-5 stays open). *Replaced by D-028.*
- A rejected answer is retried with a list of the failed checks; after `annotation.max_retries` the article is marked failed for that step. An answer is accepted or rejected as a whole. *Replaced by D-027 for the analyst: failed passages and statements are set aside, the rest is accepted.*
Reason: JSON can be checked by a schema and by code. Grouping statements by passage gives the shared passage identifier of D-003 directly. An action list is the narrowest possible form for the reviewer and makes its limits easy to enforce. Retrying with the reasons lets the model correct a copying error instead of repeating it.
Consequences: full specification in `docs/output-format.md`. Checking code and tests are written in the next stage.

**D-023 — Provisional scope rulings for the pilot (answers Q-1 to Q-3 provisionally; adds Q-7)**
Date: 2026-11-22. Status: approved for the pilot at ✋2 (2026-11-22); to be reviewed after the pilot.
Decision: the prompts apply these rules:
1. **Performers (Q-1)** are not creators. Judgements of actors, singers, dancers, instrumentalists, conductors and of particular performances are not annotated. A theatre or concert notice that judges the play, the opera or the music itself, or its author or composer, is annotated.
2. **Other targets (Q-2).** Translations are works, and the translator is their creator. Exhibitions, concerts and theatres as events or institutions are not annotated, nor is the physical book (price, paper, printing). A judgement of a particular work shown at an exhibition is annotated.
3. **Boundary cases of art (Q-3).** Opera, oratorio and songs are `music` (the example given in `AGENTS.md`, section 3). Plays are `theatre`. Book illustrations are `visual art`. `other` stays, with a required note.
4. **Books of every kind (new Q-7)** count as works: histories, biographies, travels, sermons, essays, scholarship, as well as fiction and poetry. Their `art` is `literature`, and `work_genre` records the kind of book ("history", "sermon"), so that non-fiction can be filtered out later. A judgement of a person's arguments as expressed in a work is a judgement of the work.
Reason: the corpus sample shows all these cases often. The Leader's literature section and the Monthly Repository review every kind of book, and its theatre and music notices are largely about singers and actors. Without a rule the analyst would decide case by case. Excluding performers keeps the `creator` field to creators in the sense of the guidelines; the alternative, annotating performers, would need a way to tell them apart, which the guidelines do not have, and adding a field would be a new category (AGENTS.md, section 9). For books, recording the kind of book in `work_genre` keeps all information without inventing a category.
Consequences: Q-1 to Q-3 remain listed as open until confirmed. Statement counts for music and theatre will be low where notices are mostly about performers. The pilot report will say how often each rule applied, where this can be seen from the data.

**D-024 — Evidence for verbatim fields; what the reviewer may delete**
Date: 2026-11-22. Status: adopted (approved at ✋2, 2026-11-22).
Decision:
- `quote` and `evaluative_expression` carry no evidence level in the LLM answer: they are verbatim text checked by code, and the code records them as `observed`. `note` is a remark, not a claim. An empty field is not a claim and has no level; an empty `quoted_source` means the critic's own voice.
- The reviewer may delete a whole statement, or the fields `creator`, `work_title` or `work_genre` on their own. `art`, `polarity`, `sarcastic`, `criterion` and `quoted_source` may be downgraded but not deleted on their own; if one of them is wrong, the reviewer deletes the statement. `quote` and `evaluative_expression` can be neither deleted nor downgraded.
- When an evaluation belongs to a quoted source but `quoted_source` is empty, the reviewer deletes the statement.
Reason: `evidence-and-review.md` says that the quotation is observed by definition; the evaluative expression is also verbatim and checked against the quotation. A statement without polarity, criterion or art is not a complete evaluation, and deleting `quoted_source` would turn someone else's judgement into the critic's own, which is a change of value that D-005 forbids. This narrows the reviewer's right to "delete a claim" for these five fields.
Consequences: enforced by the reviewer checks (`docs/output-format.md`, section 5.2).

**D-025 — Running the LLM steps and checking their answers (stage 6)**
Date: 2026-11-22. Status: adopted.
Decision:
- **Commands.** `uv run ncse analyse` and `uv run ncse review` send the requests (stages 4 and 6); each answer is checked at once, because a rejected answer must be retried. `uv run ncse check analyst` and `uv run ncse check reviewer` (stages 5 and 7) check every stored answer again without any request, confirm that each stored result is exactly what the checks produce from the raw answer, and write a report with statistics to `reports/`. `uv run ncse estimate` estimates requests and tokens. `--sample` runs any of them on `corpus_sample/`.
- **Instruction adherence is checked for both steps** (project owner, ✋2). Besides the schema and the content rules of `docs/output-format.md`, an answer is rejected when it is not a bare JSON object (text around it, Markdown code fences), repeats a key, was cut off at the length limit, has a name or title wrapped in quotation marks or underscores or with spaces around it, or has an empty note, assumption or reason. These follow explicit instructions in the prompts. Instructions that concern interpretation (passage order, repeated quotes or statements, observed values not found in the text) are flagged, not rejected.
- **Storage.** One JSON record per article and step in `data/annotation/<full|sample>/<step>/`. It holds every attempt: the messages sent (the instructions are identified by prompt version and SHA-256 checksum rather than copied), the raw answer, token counts, the model named by the service, check errors and flags, and the accepted result. The record is saved right after each answer and before it is checked. A run summary with the settings is written to `data/annotation/<mode>/runs/`.
- **Resuming.** Accepted and failed articles are skipped. An answer saved but not yet checked is checked on resume, not requested again. An interrupted round of attempts continues where it stopped. `--retry-failed` gives failed articles one new round; old attempts are kept.
- **Errors of the service.** Network errors and "busy" answers (HTTP 408, 409, 429, 5xx) are retried after a pause that doubles each time; they do not count as attempts. Any other refusal (wrong key, unknown model) stops the run; finished work is kept.
- **Reviewer.** Articles whose accepted analyst answer has no statements are not sent; they are recorded as reviewed with no actions. A review remembers the checksum of the analyst result it reviewed; if the analyst result changes, the old review is reported, not reused.
- **Corpus version.** A fetched corpus is identified by its release tag, a locally built one by its build commit. `corpus_sample/` is recorded as `corpus-v1.0 sample`: its 24 texts were compared with corpus-v1.0 (built at commit 4e2af63) and are identical.
- **Client.** The LiteLLM service is called through its OpenAI-compatible HTTP interface with Python's standard library, so no extra package is needed. `jsonschema` was added to check the schemas. The service address and key are read from the environment variables named in `config.yaml` (`llm`).
Reason: the owner asked that both steps be checked algorithmically for format and instruction adherence. Saving before checking, and checking saved answers on resume, means a paid answer is never lost or bought twice. Re-checking in a separate command makes stages 5 and 7 runnable on their own and catches any change to the stored data.
Consequences: code in `src/ncse/checks.py`, `quotes.py`, `prompts.py`, `llm.py`, `annotate.py`, `checkreport.py`, `estimate.py`; tests in `tests/test_checks.py`, `test_prompts.py`, `test_annotate.py`, `test_llm.py` (fake LLM, no network). Not yet run against the real service: the models are not chosen yet.

**D-026 — Retrying an answer that was cut off at the length limit**
Date: 2026-11-22. Status: adopted.
Decision: when an answer was cut off at the length limit (`max_tokens`), the retry sends back only its first `annotation.retry_echo_chars` characters (2,000), marked as shortened, and the feedback message adds: "Only the beginning of your answer is shown above. Do not write any text outside the JSON object and do not repeat yourself." Other rejected answers are still sent back whole. The full answer is always kept in the record; the shortened version sent is recorded with the attempt's messages.
Reason: in the first smoke test (`meta-llama-3.1-8b-instruct`) the model never wrote JSON. It repeated one sentence until it reached the length limit (about 70,000 characters per attempt). The retry sent all of it back, so the request grew from about 5,000 to 21,000 input tokens and the model fell into the same loop again. The beginning is enough to show the model what went wrong. An answer that was not cut off is bounded by `max_tokens`, and the model needs it in full to correct its quotations.
Consequences: code in `annotate.py` (`StepRunner.echo`) and `checks.retry_message`; tests in `tests/test_annotate.py` and `tests/test_checks.py`.

**D-027 — Accepting the good part of an analyst answer; stopping repeated retries**
Date: 2026-11-22. Status: adopted (project owner, after the smoke tests). Replaces the "accepted or rejected as a whole" rule of D-022 for the analyst.
Decision:
- Only problems with the analyst's answer as a whole (empty, not a bare JSON object, repeated keys, cut off, not valid JSON, not matching the schema) reject it and lead to a retry.
- A passage whose quote cannot be found is set aside together with its statements. A statement that breaks a rule (expression not in its quote, no target, assumption rules, `other` without a note, empty note, wrapped or padded names) is set aside alone. Failed items are stored in the result's `failed` list with their reasons and with what the model wrote, counted in the log and listed in the stage report. The rest of the answer is accepted **without a retry**. Items keep their numbers, so `p04` stays `p04` when `p03` is set aside.
- If the model returns exactly the same answer as in the previous attempt, no further attempt is made and the article is marked failed with that reason. This is also checked when a stopped run resumes. Empty answers do not count as the same answer (added 2026-11-23): they come from the model's reasoning running in a loop until it stops, which happens at random, and in both pilots a retry after an empty answer usually succeeded.
- The reviewer's answer is still accepted or rejected as a whole (D-005: any action outside its limits rejects it). The reviewer sees only accepted statements.
- Analyst `max_tokens` raised from 8,000 to 32,000 (`config.yaml`).
- The analyst prompt v1 was changed in two sentences that said the whole response is rejected for any mismatch. They now say that a response in the wrong format is rejected and that a passage or statement breaking a rule is dropped. The version stays `v1` at the owner's request: the change was made before the pilot, after two smoke tests on 2 articles. The records of those tests carry the earlier checksum (`4ed4f3f892da…`); the new text has `2c35cb8b8a00…`. Short smoke tests before the pilot do not freeze a prompt version (`prompts/README.md`).
Reason: in the second smoke test (`gwdg/qwen3-30b-a3b-instruct-2507`) both articles failed. One answer had 30 statements, of which 2 failed a check, so all 30 were lost. The other model copied its rejected answer unchanged in both retries, so each retry cost a full answer and gained nothing. One article produced 30 statements in about 8,000 output tokens, so 8,000 was too low; the longest article is about 6,100 words. Rule 6 of `AGENTS.md` is kept: no failure is dropped silently, and none is fixed by hand.
Consequences: code in `checks.check_analyst` and `annotate.py`; the stage report (`ncse check analyst`) gets sections on failed items and on how quotations matched. Tests in `tests/test_checks.py` and `tests/test_annotate.py`. Applied to the smoke-test answers, the new checks would accept 30 of 30 statements of LDR-1851-05-17-011 and 23 of 30 of LDR-1850-11-30-005 (7 without a target).

**D-028 — Quotation matching tolerance (answers Q-5)**
Date: 2026-11-22. Status: adopted (project owner). Replaces the tolerance of D-022.
Decision: a quotation, and an evaluative expression within its quotation, is matched at the strictest of three levels that succeeds, and the level is recorded with the passage (`quote_match`) and the statement (`expression_match`):
- *exact*: only whitespace differs (as in D-022);
- *normalised*: the same letters and digits in the same order, with all other characters and capitals ignored. This accepts differences in punctuation, the form of quotation marks and dashes, line breaks, hyphenation at line ends and capitals, as long as the words stay the same. Accepted without a flag;
- *approximate*: a few letters or digits differ (inserted, deleted or replaced), at most `quotes.max_char_errors` = 3 and at most `quotes.max_error_share` = 5% of the letters and digits of the quoted text, so phrases under 20 letters get no allowance. Meant for silently corrected OCR errors and typos. Accepted with a flag (`approximate_quote`, `approximate_expression`).

A normalised or approximate match must start and end at word boundaries in the text. Inside a match, word divisions are not checked ("a part" matches "apart"), because a broken word ("appre-⏎elated") must match the joined one. Whatever the level, the code records the exact source text of the match (`quote_source`, `evaluative_expression_source`), and the dataset uses that text, never the model's copy. The tolerance used is stored with each result, so the re-check (`ncse check analyst`) uses the same values even if `config.yaml` changes later. The "observed but not found" flag also compares at the normalised level. The prompt still asks for verbatim copies.
Reason: in the smoke test, quotations failed only where the model tidied the text at a break in the corpus: it dropped a stray full stop between two text boxes ("the Minuet.⏎⏎and Saraband"), joined a broken word ("appre-elated"), and left out a semicolon inside quotation marks. None of these changes a word. The word-boundary rule was added after a test showed that "no ground for supposing" would otherwise match "any ground for supposing" with one changed letter, reversing the meaning.
Consequences: `AGENTS.md` (rule 6 and section 10) updated with the owner's approval. Code in `src/ncse/quotes.py`; settings under `quotes` in `config.yaml`; tests in `tests/test_checks.py`.

**D-029 — Stopping a run: Ctrl-C, and answers that take too long**
Date: 2026-11-22. Status: adopted; what happens to a too-slow request is changed by D-031.
Decision:
- **Ctrl-C.** The first Ctrl-C sends no new request and ends any pause before a retry. Requests already sent may finish, so that answers being paid for are saved. A second Ctrl-C quits at once; answers still on their way are then lost. Either way, the same command continues the run later.
- **Too slow for the service.** A gateway error (HTTP 502 or 504) or a time-out that comes after at least `llm.slow_failure` seconds (120) is not retried: the run stops with a message saying that the model needs longer than the service allows for one answer. Quick 502 and 504 answers are still retried as "busy".
- HTTP 401 and 403 errors that mention the model get a hint that the key may not be allowed to use this model, even if `uv run ncse models` lists it.
Reason: in a smoke test with `jlu/qwen3.8-27b`, a reasoning model, each request ended after about 300 seconds with HTTP 502, apparently the service's time limit for one answer. The code took this for a busy service and retried with growing pauses, so the run would have taken more than half an hour to give up. Ctrl-C did not stop it, because the main program waited for the requests running in the background.
Consequences: code in `llm.py` and `annotate.py` (`StepRunner.interrupted`); setting `llm.slow_failure` in `config.yaml`; tests in `tests/test_llm.py` and `tests/test_annotate.py`.

**D-030 — Turning reasoning down**
Date: 2026-11-22. Status: adopted (project owner).
Decision: each step has two more settings in `config.yaml`. `reasoning_effort` (`none`, `minimal`, `low`, `medium`, `high`, or `null` for the model default) is the standard option, which the LiteLLM service translates for models that support it. `extra` passes further options to the service unchanged, for models that are switched another way, e.g. `{chat_template_kwargs: {enable_thinking: false}}` for Qwen3 models served by vLLM. `extra` may not set what the code or the named settings set (model, messages, temperature, max_tokens, response_format, reasoning_effort, stream). Both are sent with every request and recorded with every attempt. The log now counts reasoning tokens, which the service reports as part of the completion tokens.
Reason: reasoning models (`jlu/qwen3.8-27b`) thought for longer than the service allows for one answer (D-029), and as reviewer used up to 8,000 tokens on thinking. Whether a model honours either setting can only be seen in a run, through the reasoning-token count.
Consequences: `request_settings` in `annotate.py`; tests in `tests/test_annotate.py`. Both settings are off (`null`, `{}`) by default.

**D-031 — A too-slow article fails alone; the model's reasoning is kept**
Date: 2026-11-22. Status: adopted (project owner). Changes D-029.
Decision:
- When the service gives up on a request after a long wait (D-029), only that article is marked failed, with the reason and the time in the record (`slow_failures`); the run goes on with the other articles. It is not retried in the same run, because the same request would take as long and fail the same way. After `annotation.max_slow_in_row` (3) such failures in a row, the run stops: then the model as a whole is too slow. `--retry-failed` tries the failed articles again, for example after turning reasoning down (D-030).
- If the service returns the model's reasoning text (`reasoning_content` or `reasoning`), it is stored with the attempt (`reasoning`), so that a reader can see why a statement was made, kept or deleted. It is not checked and does not enter the data.
Reason: in the smoke tests a 10,000-character article took the analyst 4 min 16 s, close to the service's limit of about 300 s, and some articles are longer; one long article should not stop a pilot or a full run. The reviewer accepted all 27 statements of the second analyst smoke test without a single action; without its reasoning there was no way to see whether it had considered the borderline cases.
Consequences: `SlowAnswer` in `llm.py`; `StepRunner.too_slow` in `annotate.py`; tests in `tests/test_llm.py` and `tests/test_annotate.py`.

**D-032 — Models for the pilot (provisional)**
Date: 2026-11-22. Status: provisional, for the pilot (project owner); to be reviewed with the pilot results at ✋3.
Decision: analyst and reviewer both use `jlu/qwen3.8-27b-fast`, a reasoning model, with reasoning left on (`reasoning_effort: null`, `extra: {}`), `temperature: 0`, `max_tokens: 32000` and `response_format: json_object`.
Reason: in the smoke tests it was the only model that kept both recall and the scope rules (Don Giovanni notice: 6 of 6 clear evaluations, none out of scope). A small model produced no JSON; a mid-sized model without reasoning ignored the scope rules (26 of 28 statements deleted by the reviewer); the regular variant of the same model exceeded the service's time limit; another large model was not accessible with our key. `reasoning_effort: low` had no effect; turning reasoning off saved about a quarter of the analyst's time but lost recall (4 of 6) and added 13 out-of-scope statements. As reviewer the model's deletions were sound; with a strong analyst it made none, which may mean it shares the analyst's blind spots: read its stored reasoning on borderline cases in the pilot.
Consequences: the pilot is run with `scripts/pilot.sh`. Watch in the pilot: articles failed as too slow (long articles), the reviewer's deletion rate, and output tokens per article for the cost estimate of the full run.

**D-033 — A stricter reviewer (prompt v2)**
Date: 2026-11-23. Status: decided (project owner, ✋3 discussion), effect to be measured on the pilot sample.
Decision: the reviewer uses `prompts/reviewer/v2/`. It differs from v1 only in the instructions on how to decide: v1 said "When in doubt, leave the statement alone" and "most statements should need no action"; v2 says the reviewer is the quality filter, should not assume the analyst is right, and should delete or downgrade when in doubt. It names four questions to ask of every statement (is it an evaluation at all, is the polarity right in the sentence's period sense, is the criterion right, is the evidence level too high) and adds a second invented example (a plot description and an ironic charge of borrowing, both deleted). The limits on the reviewer (delete and downgrade only) are unchanged.
Reason: in the pilot (prompt v1) the reviewer acted on 7 of 237 statements. Its stored reasoning shows it considered clearly wrong statements several times and kept them because of the "when in doubt" rule: "Egmont comes in his splendour" (plot description) and "Scott appropriated [the scene] in Kenilworth with a coolness not surpassed by Dumas himself" (a charge of plagiarism recorded as positive aesthetic praise). The owner: a strict filter is the point of having a reviewer.
Amended the same day, before any wider use and keeping the version number (owner's request): the v2 re-run on the pilot sample deleted fields where v1 had lowered their level, and made no downgrades at all, losing the inferred/suggested distinction. The instructions now say that strictness means fairness: choose the smallest action that fixes the problem; delete when a statement or value is wrong, downgrade when it may be right but rests on weaker evidence; a field that is a plausible guess is downgraded to `suggested`, not deleted. The first v2 run and the amended one are told apart by the checksum of the instructions recorded with every answer (`0f831b21ba4c` before; `62ec31b5e663` after, including the section on parts of D-034).
Consequences: `config.yaml` → `annotation.reviewer.prompt_version: v2`. The v1 pilot reviews are kept for comparison (`data/annotation/sample/reviewer-v1/`); the sample is reviewed again with v2 and the two compared statement by statement. Watch for over-deletion: clear evaluations of works deleted.

**D-034 — Long articles are annotated in parts and joined back**
Date: 2026-11-23. Status: decided (project owner: split during processing, not in the corpus; join the data of one article back for analysis; send context with each part).
Decision: an article longer than `annotation.max_part_chars` (6,000 characters) is sent to the analyst in parts, cut at paragraph breaks (preferably after the end of a sentence) into the smallest number of roughly equal parts within the limit. Each part after the first is sent with context that is not to be annotated: the article's first 1,500 characters and the 1,500 characters before the part (`context_opening_chars`, `context_before_chars`). Quotes must come from the part. Each part has its own record and attempts; when all parts are done, they are joined into the article's record, numbered and positioned over the whole article, with the part of every passage recorded. The reviewer reviews the same parts, each with only its own statements. The article is accepted only when all its parts are; `--retry-failed` resends only failed parts. New prompt versions carry a second template for parts: analyst `v2` (v1 plus section 6a on parts) and reviewer `v2` (section 2a). Details: `docs/output-format.md`, section 1a.
Reason: in the pilot the analyst wrote about 2.5 output tokens per character (up to 3.7), mostly reasoning, at about 100 tokens per second. An 8,012-character article failed because the service gave up after 300 s, and a 7,726-character one needed 28,793 tokens, close to the 32,000 limit. Projected on the corpus, about 540 articles would exceed the time limit and about 370 the length limit. At 6,000 characters a part needs at most about 22,000 tokens. The cost: 1,276 of 5,375 articles are split, into 3,097 parts, so 7,196 requests instead of 5,375, with about 1.35 million tokens of context and 1,821 more copies of the instructions (about 8 million input tokens); output tokens should stay about the same. Context is sent because a review's book and author are usually named only at its start.
Consequences: `src/ncse/parts.py` (split, context, join); part records in `<step>/parts/`; `annotate.py` and `checkreport.py` handle them; `estimate` counts parts; tests in `tests/test_parts.py`. Changing `max_part_chars` after parts have been stored is refused, since the stored parts would no longer match. Possible effects to watch: statements whose evaluation spans a part boundary, and the same judgement recorded in two parts.

## Open questions for the project owner

These should be settled during or after the pilot, then recorded as decisions.

Q-1 to Q-3 and Q-7 have provisional answers for the pilot in D-023.

- **Q-1. Performers.** Do evaluations of actors, singers and musicians count as evaluations of "creators"?
- **Q-2. Other targets.** How are evaluations of exhibitions, theatres, concerts as events, editions and translations treated?
- **Q-3. The `other` category for art.** Opera could count as music or theatre, and book illustration as literature or visual art. Which rules apply to such boundary cases, and does `other` stay as a category?
- **Q-4. Selection beyond the topic label.** *(Answered: D-018.)* Should texts labelled with other topics (e.g. *Religion*, *Education*) that contain reviews be added? If so, how are they identified?
- **Q-5. Quotation matching tolerances.** *(Answered: D-028.)* Which trivial differences may the quotation check ignore, beyond whitespace and line breaks?
- **Q-6. Text the OCR model invented.** *(Answered: D-017.)* NCSE v2.0 was read by an image-to-text model, which sometimes adds text that is not on the page: invented newspaper headers (for example "TUESDAY, AUGUST 20, 1861" on an 1851 page), sentences repeated in a loop, and remarks addressed to the user ("Certainly! Below is the extracted table…"). Should such passages be detected and excluded, flagged in the metadata, or left alone? For now they are left in the text unchanged (D-006).
- **Q-7. Non-fiction books.** Do evaluations of histories, sermons, travels, scientific and scholarly books count, with `art` = `literature`? Provisionally yes (D-023); `work_genre` records the kind of book.

**Notes on Q-4 from the data inspection (2026-11-22).** The Leader opens its literature section with the motto "Critics are not the legislators, but the judges and police of literature". Boxes with this motto are sometimes labelled *education* or *religion* rather than arts. *Monthly Repository* reviews of theological books ("Art. III.—Religious Liberty Stated and Enforced… By Thomas Williams") are labelled *religion*. Section headings and review formulas ("Art. N.—", "By … pp.") could find such reviews. See `reports/01-data-inspection.md`.
