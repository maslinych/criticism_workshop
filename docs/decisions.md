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
Consequences: commands in `README.md` and `CLAUDE.md`.

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
Date: 2026-11-22. Status: provisional (chosen by the project owner from the options in the inspection report; review after the pilot).
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

## Open questions for the project owner

These should be settled during or after the pilot, then recorded as decisions.

- **Q-1. Performers.** Do evaluations of actors, singers and musicians count as evaluations of "creators"?
- **Q-2. Other targets.** How are evaluations of exhibitions, theatres, concerts as events, editions and translations treated?
- **Q-3. The `other` category for art.** Opera could count as music or theatre, and book illustration as literature or visual art. Which rules apply to such boundary cases, and does `other` stay as a category?
- **Q-4. Selection beyond the topic label.** Should texts labelled with other topics (e.g. *Religion*, *Education*) that contain reviews be added? If so, how are they identified?
- **Q-5. Quotation matching tolerances.** Which trivial differences may the quotation check ignore, beyond whitespace and line breaks?
- **Q-6. Text the OCR model invented.** NCSE v2.0 was read by an image-to-text model, which sometimes adds text that is not on the page: invented newspaper headers (for example "TUESDAY, AUGUST 20, 1861" on an 1851 page), sentences repeated in a loop, and remarks addressed to the user ("Certainly! Below is the extracted table…"). Should such passages be detected and excluded, flagged in the metadata, or left alone? For now they are left in the text unchanged (D-006).

**Notes on Q-4 from the data inspection (2026-11-22).** The Leader opens its literature section with the motto "Critics are not the legislators, but the judges and police of literature". Boxes with this motto are sometimes labelled *education* or *religion* rather than arts. *Monthly Repository* reviews of theological books ("Art. III.—Religious Liberty Stated and Enforced… By Thomas Williams") are labelled *religion*. Section headings and review formulas ("Art. N.—", "By … pp.") could find such reviews. See `reports/01-data-inspection.md`.
