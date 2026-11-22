# Project status

Update this file at the end of every work session: what was done, what is next, and what problems came up. Keep entries short. Record decisions in `docs/decisions.md`, not here.

## Stages

| # | Stage | Status | Notes |
|---|---|---|---|
| 1 | Set up repository, environment, configuration | done | Python + uv (D-009); `config.yaml` |
| 2 | Acquire NCSE v2.0 data | done | 3 files, checksums OK; `reports/acquire-manifest.json` |
| 3 | Inspect data structure; test selection rule; rebuild articles; write prepared corpus (`.txt` files + `metadata.csv`) | done, awaiting ✋ | 5,127 articles; report `reports/01-data-inspection.md`; 24-article sample in `corpus_sample/` |
| 4 | Publish corpus release `corpus-v1.0`; fetch stage; commit raw and corpus samples; test fetching from a fresh clone | not started | |
| 5 | Draft analyst and reviewer prompts and output format | not started | ✋ approval needed |
| 6 | Scripts for LLM calls, output checks, tests | not started | |
| 7 | Pilot run (20–30 articles) | not started | ✋ results reviewed by project owner |
| 8 | Full annotation run | not started | cost estimate first |
| 9 | Assemble dataset and data dictionary | not started | |
| 10 | Summary statistics | not started | |

## Next steps

- Project owner: review `reports/01-data-inspection.md` (✋1) and answer its questions (rebuild rule, Q-4, Q-6, balance between periodicals).
- Then stage 4: raw NCSE sample (a few hundred boxes, about a dozen complete articles) as test data for stages 2–3; corpus release `corpus-v1.0`; fetch stage.

## Problems and observations

- 2026-11-22: an NCSE entry is a layout box, not an article; the labels are assigned per box and are noisy (D-012).
- *The Leader* exists in two editions (LDR, CLD) with mostly the same text; only LDR is used (D-010).
- The OCR model sometimes invents text (headers with wrong dates, repeated sentences, passages that cannot belong to the issue's date). Left in place for now; open question Q-6.
- Many rebuilt articles are fragments (one text box, or no heading); some selected texts are book advertisements.
- The *Monthly Repository* gives about 0.5 million words, *The Leader* about 3 million.
