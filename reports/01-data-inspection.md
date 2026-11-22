# Data inspection and prepared corpus: report for approval point ✋1

> **Revised after the project owner's answers (2026-11-22).** Sections 1–7 describe the first version of the corpus (rebuild rule D-012) and the questions asked about it. **Section 8 describes the current corpus**: articles rebuilt as whole units between headings (D-016), invented OCR text left out (D-017), selection not widened (D-018). The sample in section 6 has been replaced by the one in section 8.

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

**Sample of the first version** (replaced; see section 8 for the current sample) (`corpus_sample/`, committed; 12 articles per periodical, chosen at random by code among articles of at least 1,500 characters). The comments are my reading of each text:

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

## 8. Revised corpus after the project owner's answers

The answers given, and what was done:

| Question | Answer | What changed |
|---|---|---|
| 1. Rebuild, fragments, false positives | False positives are acceptable but must not dominate the corpus. Fragments are worse, because they distort the context. Complete them into whole articles if possible. | New rebuild rule D-016 (below) |
| 2. Q-4, widening the selection | Fiction matters more than political or religious writing. Do not inflate the corpus; widening is fine only if it can be done cleanly. | Tested, not adopted (D-018) |
| 3. Q-6, invented text | Exclude it, and record what was excluded and why. | Detection and exclusion list (D-017) |
| 4. Balance between periodicals | No balancing. | Nothing |

### 8.1 Invented text (D-017)

A box is left out as invented text when the OCR model reached its output limit of 2,000 tokens for every part of the box, or when at least 30% of its 8-word sequences repeat. In the issues used this applies to 1,152 boxes of the *Monthly Repository* (8% of its characters) and 4,810 boxes of *The Leader* (15%). The 527 of them that lie inside an article, or would have formed one, are listed in `excluded_boxes.csv` with the reason (3.3 million characters, about 0.55 million words, no longer sent to the LLM). An example row:

```
ncse_entry_id: MRP-1832-03-02_page_45_B0C1R2
reason:        output limit: the OCR model wrote 2000 tokens, the limit of 2000 per part
n_chars:       8424
selected:      yes
article_id:    MRP-1832-03-02-001
text_start:    THE POOR AND THEIR POETRY*. *This is a subject …
```

**Not caught:** short invented passages that do not loop. In the new sample, two such passages remain: a note on Trelawny's life of Byron (published 1858) in an 1851 issue, and news of the death of King Theodore of Abyssinia (died 1868) in an 1857 issue. As an extra signal, `rebuild_notes` now flags any box that mentions a year more than one year after the issue date (219 articles). These boxes are flagged, not excluded, because most such years are OCR misreadings (1881 for 1851). Neither of the two examples mentions a year.

### 8.2 Whole articles (D-016)

Headings are now also found **inside** text boxes. In *The Leader* most review titles are the first words of an ordinary text box ("REED ON ENGLISH LITERATURE. English Literature from Chaucer to Tennyson. By Henry Reed."), not separate title boxes. Three kinds are recognised: a phrase in capitals ending in a full stop, a numbered review ("Art. VI.—"), and a book heading (title, "By" and author, place, format or pages). The text from one heading to the next is a *unit*. A unit containing a selected box is taken **whole** if it spans at most 3 pages and either opens with a box carrying the arts topic label (of any text type except advert) or has at least half its text selected. Other units contribute only their selected parts, as before.

| | *Monthly Repository* first version | *Monthly Repository* now | *The Leader* first version | *The Leader* now |
|---|---:|---:|---:|---:|
| articles | 1,226 | 1,240 | 3,901 | 4,135 |
| words | 489,742 | 521,683 | 3,046,132 | 3,373,664 |
| median words per article | 185 | 218 | 495 | 562 |
| taken as whole units | — | 397 | — | 3,059 |
| starting at a title box or a heading in the text | 488 | 612 | 2,553 | 3,243 |
| starting without any heading | 738 | 628 | 1,348 | 892 |
| only one text box | 725 | 619 | 1,763 | 1,466 |

In *The Leader* three articles in four are now whole units. Most are complete reviews that were fragments before, for example of Wilkie Collins's *The Queen of Hearts*, Eugène Sue's *Les Enfants de l'amour* and Plato's *Republic*. The total grew by 11% (LDR) and 7% (MRP) despite leaving out the invented text. The *Monthly Repository* gains less: its layout misses many headings, so 417 of its units run over more than 3 pages and still give only their selected parts. Completing those would need a better way to find headings there.

Known weaknesses:

- When the next heading is missed, a whole unit can run on into an unrelated item. Three of the 12 Leader sample articles end with an unrelated paragraph (in one of them, invented text).
- A list of new books opens with a book heading and can be taken whole (one sample article).

### 8.3 Selection not widened (D-018)

A clean test of widening was to take every unit that opens with a book heading but has no selected box. That would add about 244,000 words to the *Monthly Repository* (+47%), almost all reviews of sermons and theological tracts. It would add about 212,000 words to *The Leader* (+6%), mostly history, travel, science and politics, with a few news paragraphs caught by mistake. Few of these texts are reviews of fiction, so the selection stays as it is.

### 8.4 New sample

`corpus_sample/` (12 articles per periodical, drawn at random among articles of at least 1,500 characters, same seed as before). The comments are my reading of each text.

| Article | Pages | Words | Boxes | Selected share | Whole unit | Heading | Comment |
|---|---|---:|---:|---:|---|---|---|
| LDR-1850-11-30-005 | 15;16 | 1661 | 9 | 0.79 | yes | LITERATUR. Critics are not the legislators, b | opening of the literature section (motto), then book reviews |
| LDR-1851-05-17-011 | 18 | 536 | 3 | 0.99 | yes | \| \| DON GIOVANNI. | opera review (*Don Giovanni*) |
| LDR-1851-09-27-002 | 14;15 | 1458 | 8 | 0.62 | yes | (heading in capitals) | literature column; first box ("The *Times* says…" on Trelawny's *Byron*, published 1858) is probably invented and was not caught (D-017) |
| LDR-1852-01-17-008 | 21 | 442 | 4 | 0.76 | yes | . DREARY LANE! . | theatre column ("Dreary Lane!") |
| LDR-1852-06-05-001 | 16 | 1175 | 7 | 0.54 | yes | A THOUGHT OR TWO ON THE BOOK QUESTION. | letter on the book trade; ends with part of another letter (missed heading) |
| LDR-1852-06-05-008 | 22;23 | 1918 | 12 | 0.55 | yes | EGMONT AND THE GERMAN ACTORS. | theatre review (*Egmont* and the German actors) |
| LDR-1854-06-24-002 | 14 | 655 | 4 | 0.98 | yes | KOSSUTH'S EDITION OF HIS OWN SPEECHES. (To th | Holyoake's letter on a cheap edition of Kossuth's speeches: publishing, little criticism |
| LDR-1855-07-28-001 | 15 | 1302 | 4 | 0.63 | yes | (heading in capitals) | literature section: German High Art, then notices |
| LDR-1856-03-08-005 | 16 | 1144 | 4 | 0.99 | yes | . - Chassez le naturel, il revient au galop | essay on criticism (Longinus) |
| LDR-1857-02-14-007 | 20;21 | 1297 | 5 | 0.18 | yes | (heading in capitals) | review of the novel *Lucy Aylmer* and other notices; ends with a news paragraph probably invented (death of King Theodore, 1868); a loop box was left out |
| LDR-1858-05-15-003 | 10 | 1068 | 3 | 0.70 | yes | (heading in capitals) | Musical Union concert notices; ends with an unrelated paragraph (missed heading) |
| LDR-1859-01-08-008 | 23 | 1021 | 5 | 0.95 | yes | No. 459, January 8, 1859.] Fine Arts. | Fine Arts column |
| MRP-1806-04-02-002 | 28 | 530 | 3 | 0.13 | no | 196 Original Letters by Dr. Franklin. | letters of Benjamin Franklin: false positive |
| MRP-1806-04-02-004 | 53;54 | 2194 | 13 | 0.58 | yes | (heading in capitals) | "Literary" intelligence column, ending in news |
| MRP-1808-09-02-001 | 1;2 | 718 | 3 | 0.59 | no | [Continued from p. 410.] [Continued from p. 4 | part of a long article on Bishop Hurd (unit of 7 pages) |
| MRP-1808-10-02-006 | 50 | 331 | 1 | 1.00 | no | — | end of an obituary of a Greek professor: little criticism |
| MRP-1822-03-02-001 | 26;27 | 494 | 2 | 1.00 | no | — | biblical exegesis: false positive |
| MRP-1826-06-02-009 | 63;64 | 281 | 3 | 0.60 | yes | (book heading) | list of new publications: false positive |
| MRP-1830-03-02-002 | 42 | 475 | 4 | 0.73 | no | — | middle of a review of a translator of poetry |
| MRP-1831-08-02-005 | 53;54;55 | 1403 | 12 | 0.07 | yes | FRANCIS KNOWLES. | letter on a religious book; a box of invented text was left out |
| MRP-1832-03-02-001 | 44;45;46;47;48;49 | 2259 | 10 | 0.52 | no | * See Systematic Morality, vol. ii, p. 69. | essay "The Poor and their Poetry"; its first box (invented, output limit) was left out |
| MRP-1832-11-02-003 | 16 | 366 | 1 | 1.00 | no | — | part of a review of Reinhard's sermons on literary style |
| MRP-1837-08-01-006 | 68;69 | 292 | 3 | 0.65 | no | — | notice of a book by Dr Nichol (no heading) |
| MRP-1837-09-01-020 | 56;57;58 | 1180 | 8 | 0.13 | yes | (heading in capitals) | review of a tragedy, with quotations |

Of the 24: about 17 are criticism or writing about the arts, 2 are about books and publishing with little criticism, 3 are clear false positives (Franklin's letters, biblical exegesis, a list of new books) and 2 are marginal (an obituary, a letter on a religious book). False positives do not dominate. All 12 Leader articles are whole units, but only 4 of the 12 *Monthly Repository* articles are; 5 of those still start without a heading. Two articles contain invented text that was not caught; three invented boxes inside sample articles were left out (listed in `corpus_sample/excluded_boxes.csv`).

### 8.5 For approval (✋1)

- the rebuild rule D-016 and the invented-text rule D-017 for the pilot;
- leaving the selection unwidened (D-018);
- the remaining weaknesses: *Monthly Repository* fragments, run-on endings, and short invented passages that are not caught.

Then the next stage is to publish the corpus as release `corpus-v1.0`, with `excluded_boxes.csv` inside it.

