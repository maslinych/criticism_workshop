# Data inspection and prepared corpus: report for approval point ✋1

Date: 2026-11-22. All numbers come from `reports/01-data-inspection-tables.md` (made by `uv run ncse inspect`) and `reports/02-corpus-summary.md` (made by `uv run ncse prepare`). Decisions referred to as D-xxx are in `docs/decisions.md`.

## 1. What was downloaded

These files come from the NCSE v2.0 record on figshare (DOI 10.5522/04/28381610, version 1). Their checksums match the published ones, and the details are in `reports/acquire-manifest.json`.

| File | What it holds |
|---|---|
| `NCSE_v2.zip` | one table (parquet file) per periodical: the OCR text of every box on every page |
| `classification_data.zip` | the text-type and topic labels for every box, in separate tables |
| `class_mappings.zip` | the names that go with the numeric label codes |

The labels are **not** in the main text tables, so the classification files are needed for the selection rule.

## 2. What an NCSE entry is

An NCSE entry is **one box on a printed page**. A layout model drew boxes around the parts of each page, and an OCR model then read each box. Every box has:

- the issue (`issue_id`, e.g. `LDR-1852-12-11`), the page number and its place in the page's **reading order**;
- a **class**: `text` (a paragraph or block of text), `title` (a heading), `figure` (a picture) or `table`;
- its OCR **text**;
- a **text type** label (article, advert, poem/song/story, other) and zero or more **topic** labels, assigned by a machine classifier box by box.

There is **no article identifier**. In the *Monthly Repository* a text box has a median of about 770 characters and in *The Leader* about 1,300, roughly one or two paragraphs. A review of several pages consists of many boxes.

Things to know about the boxes:

- **`figure` boxes are not text from the periodical.** They hold the OCR model's description of the picture ("The image depicts a page from a 19th-century English newspaper…"). **`table` boxes** are tables re-typed by the model. Both are left out of the corpus (D-013).
- **Titles are found unevenly.** In *The Leader* a title-to-title segment usually spans one or two pages. In the *Monthly Repository* many headings were not recognised as titles. Review headings such as "*Helena. A Poem. By Thomas Wade.*" usually sit at the start of an ordinary text box. One title-to-title segment there runs to 39 pages.
- **The OCR model sometimes invents text** (open question Q-6). Examples: a newspaper header dated 1861 on an 1851 page of *The Leader*; whole invented pages ("THE FARMERS' GAZETTE … 1862") in the *Monthly Repository* front matter; a sentence repeated in a loop ("The Press has been the first to attack the Stage, and the Stage has retaliated…"); a reply addressed to the user ("Certainly! Below is the extracted table…"). Ordinary OCR errors are also present (`Tan best volume` for "The best volume", `Oxmric` for "Olympic").

## 3. Which issues are used

| Periodical | Series in NCSE | Used | Why |
|---|---|---|---|
| *Monthly Repository* | MRP (285 regular issues, 1806–1837) | yes | |
| | SMRP (13 supplements), FMRP (30 front matter/index), EMRP (1) | no | D-011 |
| *The Leader* | LDR (543 issues, 1850–1860) | yes | |
| | CLD (460 issues), FLDR (2) | no | D-010: CLD is a second edition of the same paper. 442 dates exist in both, and 30–50% of 80-character stretches of LDR text are found letter for letter in CLD. The rest differs mostly through OCR variation. |

## 4. How well the selection rule works

**The rule (D-002)**: text type = *article* AND topic includes *Arts, culture, entertainment and media*.

| | *Monthly Repository* | *The Leader* |
|---|---:|---:|
| boxes in used issues | 77,838 | 138,744 |
| boxes meeting the rule | 2,169 (2.8%) | 8,109 (5.8%) |
| of which isolated (no selected neighbour on either side) | 62% | 42% |

**Findings:**

- **The labels are noisy from box to box.** A single review often has the arts label on one box and other labels on the next. For example, the Leader's "A BATCH OF BOOKS" (1854-10-14) carries *arts* on its first box but *human interest* and *war* on the following boxes of the same review. In a review of Molière's *Don Juan* (1858-06-12), one box in the middle is typed "poem". This is why so many selected boxes are isolated.
- **Likely false positives** (selected but not criticism): booksellers' lists and advertisements for new books, obituaries of literary people, reports of meetings about copyright, sale prices of violins. See the random sample in the tables file. The analyst LLM will meet such texts and should simply find no evaluations there.
- **Likely false negatives** (criticism not selected): reviews of theological and political books in the *Monthly Repository* are labelled *religion* or *politics* (e.g. "Art. III.—Religious Liberty Stated and Enforced… By Thomas Williams"). The Leader's literature section, which opens with the motto "Critics are not the legislators, but the judges and police of literature", is sometimes labelled *education* or *religion*. There are 3,493 (MRP) and 5,182 (LDR) unselected text boxes containing review vocabulary such as "this volume", "the author", "the performance". Many are not criticism, but some are. This bears on **Q-4**: section headings and review formulas ("Art. N.—", "By … pp.") could find such reviews, but that would change the selection rule.

## 5. How articles are rebuilt (D-012, provisional)

Options were compared on the data, and the project owner chose the *hybrid* rule:

1. Each issue is cut into segments at title boxes.
2. Inside a segment, selected boxes with at most 2 unselected boxes between them form one article, and those unselected boxes are included.
3. The segment's title is attached as a heading when the article starts right after it.

For comparison, keeping only whole title segments where at least half the text is selected would have kept just 32% (MRP) and 50% (LDR) of the selected text.

**Result:**

| | *Monthly Repository* | *The Leader* |
|---|---:|---:|
| articles | 1,226 | 3,901 |
| words | 489,742 | 3,046,132 |
| median words per article | 185 | 495 |
| with a heading | 488 | 2,553 |
| only one text box | 725 | 1,763 |
| crossing a page break | 284 | 821 |
| with bridged (unselected) boxes | 376 | 1,339 |

**Known weaknesses:**

- Many articles are still **fragments**: part of a review, or a box cut off from its heading.
- A "heading" is sometimes not a real heading: a line of an epigraph ("Into their hearts.") or a page header (". PUBLIC MEETINGS.").
- The *Monthly Repository* contributes much less text than *The Leader*: 0.5 million words against 3 million.

## 6. The prepared corpus

The corpus is written to `data/corpus/full/`: 5,127 text files plus `metadata.csv`, 34 MB. It is not in git; `uv run ncse prepare` rebuilds it. The text files hold only the box texts, joined by a blank line, with the OCR unchanged. A test (`tests/test_corpus_integrity.py::test_sample_texts_match_source`) checks the sample articles letter for letter against the NCSE files.

**Sample** (`corpus_sample/`, committed; 12 articles per periodical, chosen at random by code among articles of at least 1,500 characters). The comments are my reading of each text:

| Article | Pages | Words | Boxes | Selected share | Heading | Comment |
|---|---|---:|---:|---:|---|---|
| LDR-1850-06-15-009 | 24 | 322 | 3 | 0.80 | BOOKS FOR THE MILLION | book advertisements: false positive |
| LDR-1850-11-16-004 | 16;17 | 1645 | 8 | 0.48 | EXHIBITION OF 1851. London. Oct. 20. 1850. | letters on the 1851 Exhibition |
| LDR-1853-07-30-001 | 18;19 | 1126 | 2 | 1.00 | — | end of an article, no heading |
| LDR-1854-05-27-004 | 18;19 | 1714 | 3 | 1.00 | The Aris. The Theatres. | theatre column ("The Arts. The Theatres.") |
| LDR-1854-11-11-010 | 21 | 378 | 2 | 0.99 | The Arts. — — | theatre news from Paris |
| LDR-1854-12-23-003 | 15;16 | 1550 | 6 | 0.55 | \| CHAUCER. | review of Bell's edition of Chaucer |
| LDR-1858-11-06-004 | 11 | 901 | 4 | 0.28 | TENTS AND TENT LIFE. | review of *Tents and Tent Life* |
| LDR-1858-12-24-004 | 11 | 816 | 3 | 1.00 | — | part of a review, no heading |
| LDR-1859-04-16-012 | 29 | 317 | 1 | 1.00 | — | news paragraph from Rome |
| LDR-1859-07-09-004 | 19 | 1051 | 6 | 1.00 | — | end of a book review |
| LDR-1860-01-07-005 | 13 | 1048 | 3 | 0.99 | JAN. 7, 1860. The Leader and | review of satire; heading is the running page header |
| LDR-1860-06-02-001 | 13 | 892 | 4 | 0.90 | ARTISAN ART. | article on artisan art |
| MRP-1808-03-02-003 | 32;33 | 343 | 5 | 0.40 | CORRECTED TRANSLATION OF ACTS VIII. I. XXXIII | biblical translation: false positive |
| MRP-1818-04-02-001 | 25 | 1533 | 1 | 1.00 | — | quotes a date of 1856 in an 1818 issue: probably invented by the OCR model (Q-6) |
| MRP-1825-09-02-002 | 42 | 1736 | 3 | 0.99 | — | discusses *Punch* (founded 1841) in an 1825 issue: probably invented by the OCR model (Q-6) |
| MRP-1830-06-02-002 | 46;47 | 822 | 5 | 0.51 | Art. VI.—A Practical Exposition of the Law of | review of a law book |
| MRP-1830-09-02-002 | 24;25 | 861 | 3 | 0.76 | η γλῶσσα δῆθεν ἐξῆν, ἡ δὲ φωνὴ ἀνθρωπώδης. | essay on Byron; heading is a Greek epigraph |
| MRP-1831-08-02-003 | 39 | 399 | 2 | 1.00 | — | review of Howitt's *Book of the Seasons* |
| MRP-1833-03-02-004 | 48;49;50;51 | 1762 | 8 | 0.72 | 192 Goethe's Works. | review of Goethe's works, 4 pages |
| MRP-1833-05-02-009 | 35 | 406 | 2 | 0.99 | ' I 'll break a custom. ' | part of a literary article; epigraph as heading |
| MRP-1833-09-02-007 | 75;76 | 791 | 3 | 0.91 | — | short notices of schoolbooks |
| MRP-1837-05-01-005 | 49 | 507 | 3 | 0.17 | 304. England Under Seven Administrations. | review of a political book |
| MRP-1837-05-01-008 | 64;65 | 474 | 2 | 1.00 | — | remarks on newspaper style |
| MRP-1837-10-01-004 | 18;19 | 787 | 6 | 0.72 | — | on a proposed monument / painting |

Of the 24: roughly 17 are criticism or writing about the arts, 2 are clear false positives (book advertisements, biblical translation), 2 contain text probably invented by the OCR model, and about half lack a real heading or start mid-article.

One row of `metadata.csv` in full (from the full corpus, `data/corpus/full/`):

```
article_id:      LDR-1852-12-11-003
file_name:       LDR-1852-12-11-003.txt
periodical:      The Leader
issue_id:        LDR-1852-12-11
issue_date:      1852-12-11
pages:           19
heading:         JERDAN'S AUTOBIOGRAPHY.
n_words:         1197
n_chars:         6830
n_entries:       4
selected_share:  0.468
ncse_text_types: article;article;poem/song/story;article
ncse_topics:     politics;arts_culture_entertainment_media|human_interest;arts_culture_entertainment_media;arts_culture_entertainment_media
ncse_entry_ids:  LDR-1852-12-11_page_19_B0C1R3;LDR-1852-12-11_page_19_B0C1R4;LDR-1852-12-11_page_19_B0C2R5;LDR-1852-12-11_page_19_B0C2R6
rebuild_notes:   bridged 1 unselected box(es): LDR-1852-12-11_page_19_B0C2R5
```

## 7. Questions for the project owner

1. Is the hybrid rebuild acceptable for the pilot, given the fragments and the false positives?
2. **Q-4:** should the selection be widened, for example to the Leader's literature section (found by its motto) or to *Monthly Repository* reviews found by their "Art. N.—" headings? This would recover reviews of religious and political books.
3. **Q-6:** should invented OCR text be flagged or excluded? Two of the 24 sample articles contain passages that cannot be from their issue's date.
4. The *Monthly Repository* is under-represented (0.5 against 3 million words). Should the pilot and the statistics balance the two periodicals?
5. **Cost:** the full corpus is about 3.5 million words, roughly 5 million tokens of input before prompts. The cost estimate before the full run will start from this figure.
