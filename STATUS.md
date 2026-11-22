# Project status

Update this file at the end of every work session: what was done, what is next, and what problems came up. Keep entries short. Record decisions in `docs/decisions.md`, not here.

## Stages

| # | Stage | Status | Notes |
|---|---|---|---|
| 1 | Set up repository, environment, configuration | done | Python + uv (D-009); `config.yaml` |
| 2 | Acquire NCSE v2.0 data | done | 3 files, checksums OK; `reports/acquire-manifest.json` |
| 3 | Inspect data structure; test selection rule; rebuild articles; write prepared corpus (`.txt` files + `metadata.csv`) | done, approved at ✋1 (2026-11-22) | 5,375 articles (D-016, D-017, D-018); report `reports/01-data-inspection.md` section 8; new 24-article sample in `corpus_sample/` |
| 4 | Publish corpus release `corpus-v1.0`; fetch stage; commit raw and corpus samples; test fetching from a fresh clone | in progress | `package` and `fetch` stages done and tested (D-019); release packaged in `dist/`, to be published by the project owner; raw NCSE sample not yet made |
| 5 | Draft analyst and reviewer prompts and output format | not started | ✋ approval needed |
| 6 | Scripts for LLM calls, output checks, tests | not started | |
| 7 | Pilot run (20–30 articles) | not started | ✋ results reviewed by project owner |
| 8 | Full annotation run | not started | cost estimate first |
| 9 | Assemble dataset and data dictionary | not started | |
| 10 | Summary statistics | not started | |

## Next steps

- Project owner: publish `corpus-v1.0` with the commands in `README.md` ("Publishing the corpus", steps 2–3); then pin the checksum in `config.yaml` (step 4) and test `uv run ncse fetch` from a fresh clone (step 5).
- Raw NCSE sample (a few hundred boxes, about a dozen complete articles) as test data for stages 2–3.
- Then stage 5: draft analyst and reviewer prompts and the output format (✋2).

## Problems and observations

- 2026-11-22: an NCSE entry is a layout box, not an article; the labels are assigned per box and are noisy (D-012).
- *The Leader* exists in two editions (LDR, CLD) with mostly the same text; only LDR is used (D-010).
- The OCR model sometimes invents text (headers with wrong dates, repeated sentences, passages that cannot belong to the issue's date). Boxes that hit the OCR output limit or loop are now left out and listed (D-017). Short invented passages without loops are not caught; watch for them in the pilot.
- Many rebuilt articles were fragments. Review titles in *The Leader* are usually the first words of a text box, not title boxes; with these headings recognised, 3,059 of 4,135 Leader articles are now whole units (D-016). The *Monthly Repository* still has many fragments, because its layout misses headings (417 units over 3 pages).
- 2026-11-22 (second session): owner's answers recorded as D-016 to D-018. No balancing of the two periodicals in the pilot or statistics.
- The *Monthly Repository* gives about 0.5 million words, *The Leader* about 3 million.
