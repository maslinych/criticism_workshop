# Evaluating the Arts in Nineteenth-Century Criticism

An annotated dataset of evaluative statements about artists and their works in British periodicals of the nineteenth century.

## Project goal

The aim is to build a dataset of **evaluative statements about creators and their works**, drawn from art and literary criticism in two nineteenth-century British periodicals. Creators include writers, composers, painters and dramatists. The dataset should support later **quantitative analysis** of how nineteenth-century critics judged the arts:

- which works and creators they praised or condemned;
- on what grounds (aesthetic, moral, practical, novelty, tradition);
- how often they used sarcasm or quoted other people's opinions.

The annotation is done by a large language model (LLM) working in a two-step setup:

- An **analyst** proposes annotations.
- An independent **reviewer** may only delete them or lower their confidence level.

Two requirements hold throughout the project:

1. **Traceability.** Every annotation points to an exact, verbatim passage of the source text. Nothing in the dataset is invented, paraphrased or silently corrected.
2. **Explicit evidence.** Every annotation states how directly the text supports it: whether the text *says* it, the text *implies* it, or the model *suggests* it from its own expectations.

The documentation and code should be clear enough for humanists without programming experience to follow every step. This matters as much as the dataset itself.

## Scope

**In scope**

1. Downloading the source data.
2. Selecting arts and culture texts from two periodicals.
3. Writing the scripts that send the texts to an LLM for annotation and review, and that check the results.
4. Running the annotation, first on a pilot sample, then on the full selection.
5. Assembling a readable dataset (CSV) with documentation.
6. Producing descriptive summary statistics.

**Out of scope for now**

- Statistical analysis, modelling or interpretation of the results.
- Correcting OCR errors in the source texts.
- Matching names and titles to authority files (e.g. linking "Mr. Dickens" and "Boz" to one person). The dataset should make this possible later, but it is not done now.

## Source data

The source is **NCSE v2.0**, an OCR-processed edition of the Nineteenth-Century Serials Edition:

- Prepared by Jonathan Bourne (2025).
- Licensed under CC BY 4.0.
- DOI: <https://doi.org/10.5522/04/28381610>
- Accompanying paper: Bourne, *Reading the unreadable: Creating a dataset of 19th century English newspapers using image-to-text language models* (arXiv:2502.14901).

The edition covers six periodicals. This project uses two of them:

| Periodical | Years | Notes |
|---|---|---|
| *The Monthly Repository* | 1806–1837 | Unitarian monthly that also published reviews and criticism |
| *The Leader* | 1850–1860 | Weekly with a substantial literary and arts section |

The edition comes with machine-assigned labels for each text: a **text type** (article, advert, poem/song/story, other) and a **topic** from the IPTC news subject scheme.

**Initial selection rule.** Select texts whose type is *article* and whose topic is *Arts, culture, entertainment and media*.

**Known caveats that the first stage must examine and document:**

- **The labels are unverified.** They were assigned by an LLM, not checked by people. Some criticism will be mislabelled, for example a review of a theological book filed under *Religion*.
- **Entries may not be whole articles.** The edition's units may be smaller than an article, such as single text blocks or separate title entries. Before annotation, the project must establish what an entry is and decide how to rebuild coherent articles, or other suitable units of annotation.
- **The OCR contains errors.** They stay as they are, and annotations quote the text as it appears in the edition.

Any change to the selection rule must be agreed with the project owner and recorded in `docs/decisions.md`.

**Attribution.** Any dataset derived from NCSE v2.0 must credit the original NCSE project and Bourne's edition, as the CC BY licence requires.

## Pipeline overview

Each stage reads the output of the previous one and writes its own. Every stage can be re-run, and resumed after an interruption, without redoing finished work.

1. **Acquire.** Download the NCSE v2.0 files and record where they came from, when, and their checksums.
2. **Inspect and select.** Describe the structure of the data, apply the selection rule, rebuild articles, and report what was selected and what problems were found.
3. **Prepare the corpus.** Write the selected articles out as a **readable corpus**: one plain-text file per article plus a metadata table (see "The prepared corpus" below). This corpus is the only input to annotation. Everything later refers to it, not to the original NCSE files.
4. **Annotate (analyst).** The LLM proposes evaluative statements following `docs/annotation-guidelines.md` and `docs/evidence-and-review.md`.
5. **Check.** Scripts verify the analyst's output: correct format, quotations that match the source exactly, and allowed values only.
6. **Review (reviewer).** A separate LLM call deletes or downgrades statements according to `docs/evidence-and-review.md`.
7. **Check again.** Scripts verify that the reviewer only made allowed changes.
8. **Assemble.** Build the final tables and the data dictionary.
9. **Describe.** Produce summary statistics.

## Running the pipeline

The pipeline is written in Python. Its software is managed with [uv](https://docs.astral.sh/uv/), a tool that installs the exact package versions recorded in `uv.lock` (decision D-009). Settings such as paths, the selection rule and sample sizes are in `config.yaml`.

**Once, to set up:**

```
pip install uv          # or see the uv website for other ways to install it
uv sync                 # installs Python packages into .venv/
```

**Building the corpus from source (stages 1–3):**

| Stage | Command | What it writes |
|---|---|---|
| 1. Acquire | `uv run ncse acquire` | `data/raw/` (about 1.9 GB including unpacked files), `reports/acquire-manifest.json` |
| 2. Inspect and select | `uv run ncse inspect` | `reports/01-data-inspection-tables.md` |
| 3. Prepare the corpus | `uv run ncse prepare` | `data/corpus/full/` (texts, `metadata.csv`, `excluded_boxes.csv`), `corpus_sample/`, `reports/02-corpus-summary.md` |

To refresh the raw NCSE sample (`raw_sample/`, test data for stages 2–3; needs the download), run `uv run ncse sample-raw` after stage 1.

Each command writes a log to `logs/`. Running `acquire` again skips files that are already downloaded and checked. `prepare` always rebuilds the corpus from the downloaded data and gives the same result each time.

**Tests:** `uv run pytest` runs all tests. To run one test: `uv run pytest tests/test_rebuild.py::test_page_break_is_noted`.

**Fetching the published corpus instead (normal start for annotation work):**

| Step | Command | What it writes |
|---|---|---|
| Fetch | `uv run ncse fetch` | `data/corpus/full/` (the same files as `prepare` writes, plus `CORPUS_README.md` and `FETCHED.json`) |

`fetch` downloads the release named in `config.yaml` (`release:`), checks its SHA-256 checksum and unpacks it. Running it again does nothing if that version is already in place. It does not overwrite a locally built corpus unless you add `--force`.

**Packaging the corpus for publication:** `uv run ncse package` writes `dist/ncse-arts-corpus-v<version>.zip`, its checksum file and `dist/CORPUS_README.md`. See "Publishing the corpus" below.

Later stages (annotation, review, assembly, statistics) will be added here as they are built.

## Building the corpus or fetching the published one

The source data is large: about 900 MB, delivered as a single archive. The prepared corpus built from it is small, a few MB. Once the corpus is approved, it is therefore **frozen and published** as a versioned release (see "Publishing the corpus" below), and later stages work from that published version. There are two ways to obtain the prepared corpus, and both lead to the **same** files:

- **Build from source.** Run stages 1–3 on the complete NCSE data. This code stays in the repository and must always remain runnable, so that anyone can reproduce the published corpus from NCSE.
- **Fetch the published corpus.** A single fetch stage:
  1. downloads the corpus release named in the project configuration;
  2. verifies its checksum;
  3. unpacks it where stage 4 expects the prepared corpus.

  This is the normal starting point for annotation work once a corpus version exists.

From stage 4 on, nothing depends on which way the corpus was obtained.

**Samples in the repository.** Two small samples are committed as plain files:

- **Raw sample** (`raw_sample/`): a few hundred original NCSE entries (the actual rows of the source data), covering about a dozen complete articles. It serves as test data for the selection and article-rebuilding scripts (stages 2–3), so that they can be tested and understood without the full download. It has the same folder layout as the download, with CSV files instead of parquet; `raw_sample/README.md` explains how it was drawn.
- **Corpus sample:** 20–30 prepared articles (text files plus their `metadata.csv` rows) drawn from the published corpus. It is used for quick, cheap test runs of the annotation, check and review stages (see "sample mode" below).

The samples are produced by scripts, not chosen or edited by hand, and the scripts record how they were drawn.

## The prepared corpus

Data preparation produces a corpus that people can read and check without any special tools. It has two parts:

- **A folder of plain-text files (`.txt`), one per article.**
  - Each file holds the text of the article as rebuilt from the NCSE entries, in reading order, with the OCR text left unchanged.
  - The file name is the article's identifier, which also appears in the metadata table.
  - The text files contain only text, no metadata headers. That way, quotations in the annotations can be checked directly against the file contents.
- **`metadata.csv`, one row per article.** Required columns:
  - article identifier and file name;
  - periodical;
  - issue date, volume and number where available;
  - page(s);
  - article heading or title, if any;
  - length (e.g. words and characters);
  - the NCSE labels used for selection (text type, topic);
  - the identifiers of the NCSE entries the article was built from, so that every article can be traced back to the original edition.

Any notes about how an article was rebuilt, such as entries merged across a page break or an uncertain heading, are recorded in the metadata as well.

The corpus is a deliverable in its own right. It can be read, sampled and shared (with attribution to NCSE) independently of the annotations. It is also the single, fixed input to all later stages: annotations refer to articles by their identifier and quote the text of these files.

## Publishing the corpus

The full prepared corpus is **not committed to the repository**. It is the output of the pipeline, not part of its source. Committing it would add a full copy to the git history every time it is rebuilt, and it carries its own licence (CC BY 4.0, inherited from NCSE). Instead, it is published as a **release asset** on the project's GitHub repository. The repository must be public so that the corpus can be downloaded without logging in.

**Package.** A zip file named with the corpus version (e.g. `ncse-arts-corpus-v1.0.zip`) containing:

- the folder of article text files;
- `metadata.csv`;
- `CORPUS_README.md`, a short description of the corpus:
  - source and full attribution: the NCSE project, and Bourne's NCSE v2.0 with its DOI;
  - licence (CC BY 4.0);
  - periodicals and years covered;
  - the selection rule and article-rebuilding method, in brief;
  - number of articles per periodical;
  - corpus version and date;
  - the git commit of the code that built it.

Next to the zip, a checksum file (SHA-256) is published, which the fetch stage uses to verify the download.

**Release.**

- Each corpus version is a GitHub release with a tag of the form `corpus-v1.0`. The tag points to the commit of the code that built the corpus.
- The download address therefore follows a fixed pattern: `https://github.com/<owner>/<repo>/releases/download/corpus-v1.0/ncse-arts-corpus-v1.0.zip`.
- The address of the release to use is set in the project configuration.

**Versioning.**

- A published release is **never replaced or modified**. Any correction produces a new version (`corpus-v1.1`) with a short note on what changed.
- Every annotation run records which corpus version it used, so that annotations always point to the exact texts they quote.

A DOI (e.g. by depositing the same zip on Zenodo) is optional.

**Commands.** Packaging is done by script; publishing is done by hand, by the project owner (decision D-019). `<version>` is `release.version` in `config.yaml`, e.g. `1.0`.

1. Build and package from committed code. `package` refuses to run if there are uncommitted changes or if the corpus was built at another commit.

   ```
   uv run ncse prepare
   uv run ncse package          # prints the commit the tag must point to
   cd dist && sha256sum -c ncse-arts-corpus-v<version>.zip.sha256 && cd ..
   ```

2. Push the code, then tag the commit that built the corpus (the commit printed by `package`, also in `data/corpus/full/BUILD.json`):

   ```
   git push -u origin <branch>
   git tag -a corpus-v<version> <commit> -m "Prepared corpus, version <version>"
   git push origin corpus-v<version>
   ```

3. Create the release and upload the two files, with the GitHub command-line tool `gh`:

   ```
   gh release create corpus-v<version> \
     dist/ncse-arts-corpus-v<version>.zip dist/ncse-arts-corpus-v<version>.zip.sha256 \
     --title "NCSE arts criticism corpus v<version>" --notes-file dist/CORPUS_README.md
   ```

   Without `gh`: on the repository's web page choose *Releases → Draft a new release*, select the tag, upload the two files, paste `dist/CORPUS_README.md` as the description and publish.

4. Pin the checksum: put the value from the `.sha256` file into `release.sha256` in `config.yaml` and commit. From then on `fetch` checks downloads against the value in the repository, not only against the file published next to the zip.

5. Test from a fresh clone (the repository must be public):

   ```
   git clone https://github.com/<owner>/<repo>.git test-clone && cd test-clone
   git checkout <branch>
   uv sync && uv run ncse fetch && uv run pytest
   ```

## Expected outputs

- **The prepared corpus.** The folder of article text files and `metadata.csv`, published as a versioned release (see above).
- **Samples.** The raw NCSE sample and the corpus sample, committed to the repository.
- **Statements table.** One row per evaluative statement. It holds all the fields defined in the annotation guidelines, the evidence levels and assumptions, the reviewer's decision, and a link to its article. Statements deleted by the reviewer stay in the table, marked as deleted with the reason, so that the review step itself can be studied.
- **Data dictionary.** A plain-language description of every column and its allowed values.
- **Summary statistics.** For example:
  - statements per periodical and per decade;
  - statements by art, polarity, criterion and evidence level;
  - share of sarcastic and quoted evaluations;
  - reviewer deletions and downgrades.
- **Run documentation.** Which model, settings and prompt versions produced the data.

CSV (UTF-8) is the readable format for inspection and analysis. Internal working formats are up to the implementer.

## Using the LLM

Annotation runs through the university's **LiteLLM** service, which offers an OpenAI-compatible interface to several models.

- Access credentials are read from the environment and are never written into code or committed to version control.
- The model name, settings and prompt version are recorded for every annotation.
- Before the full run, the expected number of requests and tokens is estimated and reported to the project owner.

## Development sequence and approval points

Work proceeds in this order. Steps marked ✋ need the project owner's approval before continuing.

1. Analyse the data structure and report findings, including what an entry is and how well the selection rule works. Build the prepared corpus and present a sample of article files with their metadata rows. ✋
2. Package and publish the approved corpus as release `corpus-v1.0`. Write the fetch stage, and generate and commit the two samples. Check that the fetch stage works from a fresh clone.
3. Draft the prompts for the analyst and the reviewer, and the exact output format. ✋
4. Write the scripts that run the LLM steps and check their output, together with automated tests.
5. Run a pilot on a small sample (e.g. 20–30 articles from both periodicals) and present the results for inspection. ✋
6. Run the full annotation.
7. Assemble the dataset, data dictionary and statistics.

The pipeline should also run in a cheap **sample mode** on the corpus sample, so that every stage can be tried and tested quickly, at little cost, and without the full data.

## Documents in this project

| File | What it is for |
|---|---|
| `README.md` | Project goal, scope, data and overall plan (this file) |
| `AGENTS.md` | Working rules for whoever builds the project, human or AI coding agent |
| `docs/annotation-guidelines.md` | **What** to annotate: the evaluative statement and its fields |
| `docs/evidence-and-review.md` | **How sure** we are: evidence levels and the analyst/reviewer protocol |
| `docs/decisions.md` | Log of decisions, including how particular annotation cases are handled |
| `STATUS.md` | Current progress, next steps and open problems |

The two files in `docs/` that describe the annotation are written so that they can be reused in other annotation projects with few changes.
