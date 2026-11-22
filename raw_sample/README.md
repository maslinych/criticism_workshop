# Raw NCSE sample

A small copy of the **original NCSE v2.0 data**: every box (text, title, figure and table) on 18 pages, 172 boxes in all (The Monthly Repository: 64, The Leader: 108), with their rows from the two label tables. It holds 12 complete articles and is enough to run the selection and article-rebuilding code (stages 2–3) without the 1 GB download. The tests rebuild the articles from it and compare them with `articles.csv`.

Made by `uv run ncse sample-raw` (code: `src/ncse/rawsample.py`, decision D-021). Do not edit by hand.

## How it was drawn

For each periodical, articles were chosen at random (seed 1850) from those whose unit spans at most 2 pages: 3 taken as whole units, 2 taken as selected parts of a longer unit, and 1 from which a box of invented OCR text was left out. For each chosen article, all boxes on the pages of its unit were copied, so the article comes out of the sample exactly as out of the full data. Other articles on the same pages are rebuilt too, but they may be cut off at the edge of the copied pages.

| Article (full corpus) | Chosen as | Pages copied | Words | Heading |
|---|---|---|---:|---|
| LDR-1851-04-26-010 | selected part | 14 | 399 | YEAST. |
| LDR-1858-09-11-009 | selected part | 22 | 131 | — |
| LDR-1859-04-02-002 | invented text left out | 14;15 | 557 | — |
| LDR-1859-11-12-003 | whole unit | 12 | 467 | — |
| LDR-1860-02-18-003 | whole unit | 16;17 | 1563 | . A GERMAN PASTOR. |
| LDR-1860-03-24-003 | whole unit | 14;15 | 1323 | — |
| MRP-1815-12-02-001 | invented text left out | 25;26 | 69 | Peace at last. |
| MRP-1821-02-02-002 | selected part | 44 | 334 | ----RUSSELL SCOTT. |
| MRP-1825-03-02-006 | whole unit | 59 | 150 | . LITERARY. |
| MRP-1826-04-02-007 | whole unit | 42 | 316 | — |
| MRP-1833-05-02-005 | selected part | 8;9 | 714 | 296 Henry Purcell. |
| MRP-1837-12-01-008 | whole unit | 60;61 | 270 | — |

## Files

The layout is the same as the NCSE download, with plain CSV files (UTF-8, comma-separated) instead of parquet:

- `NCSE_v2/post_processed/<periodical>_issue_PDF_files.csv`: one row per box: issue, page, place in the reading order, box class, OCR text (`content`), and the OCR model's token counts.
- `classification_data/text_type_classified/classified_<periodical>_issue_PDF_files.csv`: the text type label of each box (`predicted_class`, see `class_mappings/text_type_class_mapping.json`).
- `classification_data/IPTC_type_classified/classified_<periodical>_issue_PDF_files.csv`: the topic labels of each box (`class_<k>` = 1 when topic k applies, see `class_mappings/IPTC_class_mapping.json`).
- `class_mappings/`: the names of the label codes, copied unchanged.
- `articles.csv`: the chosen articles and what the rebuild must give for them.

To run the code on the sample, set `paths.raw` in `config.yaml` to `raw_sample`, or do as `tests/test_raw_sample.py` does.

## Source and licence

The data comes from **NCSE v2.0**: Jonathan (Jonno) Bourne (2025), *NCSE v2.0: A Dataset of OCR-Processed 19th Century English Newspapers*, University College London, <https://doi.org/10.5522/04/28381610>, licensed under CC BY 4.0. That edition is based on the **Nineteenth-Century Serials Edition (NCSE, 2008; <https://ncse.ac.uk>)**. This sample is an unchanged extract (converted from parquet to CSV) and is shared under the same licence, CC BY 4.0.
