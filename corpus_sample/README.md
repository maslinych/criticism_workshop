# Sample of the prepared corpus

This folder contains 24 articles (12 from *The Monthly Repository*, 12 from *The Leader*). They were chosen at random by `uv run ncse prepare` from the full prepared corpus. The sample is used for quick, cheap test runs of the later stages (sample mode) and for the automated tests. The full corpus is built in `data/corpus/full/` and has the same layout.

- `texts/<article_id>.txt`: the text of one article. It is rebuilt from NCSE boxes in reading order, with boxes separated by a blank line. The OCR text is left exactly as it is in the source, errors included.
- `metadata.csv`: one row per article (UTF-8, comma-separated).

## Columns of `metadata.csv`

| Column | Meaning |
|---|---|
| `article_id` | identifier: periodical code (`MRP`, `LDR`), issue date, running number of the article in the issue |
| `file_name` | name of the text file in `texts/` |
| `periodical` | periodical title |
| `issue_id` | NCSE issue identifier |
| `issue_date` | issue date (YYYY-MM-DD), taken from the NCSE issue identifier |
| `pages` | page number(s) within the issue, separated by `;` |
| `heading` | text of the title box(es) heading the article, separated by ` \| `; empty if none was found |
| `n_words` | number of words in the text file (counted at spaces and line breaks) |
| `n_chars` | number of characters in the text file |
| `n_entries` | number of NCSE boxes the article was built from |
| `selected_share` | share of the article's characters that lie in boxes meeting the selection rule (the rest are headings and bridged boxes) |
| `ncse_text_types` | NCSE text type label of each box, in order, separated by `;` |
| `ncse_topics` | NCSE topic labels of each box, in order, separated by `;`; several topics of one box are joined by `\|` |
| `ncse_entry_ids` | the NCSE box identifiers the article was built from, in reading order, separated by `;` |
| `rebuild_notes` | notes on how the article was rebuilt (bridged boxes, page breaks, missing heading, omitted figures or tables), separated by ` / ` |

How articles are rebuilt and selected is explained in `docs/decisions.md` (D-002, D-010 to D-013) and in `reports/01-data-inspection.md`.

## Source and licence

The texts come from **NCSE v2.0**: Jonathan Bourne (2025), *NCSE v2.0: A Dataset of OCR-Processed 19th Century English Newspapers*, University College London, <https://doi.org/10.5522/04/28381610>, licensed under CC BY 4.0. That edition is based on the **Nineteenth-Century Serials Edition (NCSE, 2008; <https://ncse.ac.uk>)**, whose page images are held at King's College London. This sample is a derived work and is shared under the same licence, CC BY 4.0.
