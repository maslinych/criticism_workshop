# Project status

Update this file at the end of every work session: what was done, what is next, and what problems came up. Keep entries short. Record decisions in `docs/decisions.md`, not here.

## Stages

| # | Stage | Status | Notes |
|---|---|---|---|
| 1 | Set up repository, environment, configuration | done | Python + uv (D-009); `config.yaml` |
| 2 | Acquire NCSE v2.0 data | done | 3 files, checksums OK; `reports/acquire-manifest.json` |
| 3 | Inspect data structure; test selection rule; rebuild articles; write prepared corpus (`.txt` files + `metadata.csv`) | done, approved at ✋1 (2026-11-22) | 5,375 articles (D-016, D-017, D-018); report `reports/01-data-inspection.md` section 8; new 24-article sample in `corpus_sample/` |
| 4 | Publish corpus release `corpus-v1.0`; fetch stage; commit raw and corpus samples; test fetching from a fresh clone | done | `corpus-v1.0` published 2026-11-22 (tag on commit 4e2af63, checksum pinned in `config.yaml`); fetch from a fresh clone tested; raw NCSE sample in `raw_sample/` (12 articles, 172 boxes; D-021) |
| 5 | Draft analyst and reviewer prompts and output format | done, approved at ✋2 (2026-11-22) | `prompts/analyst/v1/`, `prompts/reviewer/v1/`, `docs/output-format.md`; D-022 to D-024 (provisional) |
| 6 | Scripts for LLM calls, output checks, tests | done (not yet run against the service) | D-025; `analyse`, `review`, `check`, `estimate`; 110 tests pass, with a fake LLM |
| 7 | Pilot run (20–30 articles) | not started | ✋ results reviewed by project owner |
| 8 | Full annotation run | not started | cost estimate first |
| 9 | Assemble dataset and data dictionary | not started | |
| 10 | Summary statistics | not started | |

## Next steps

- Owner: name the LiteLLM models for analyst and reviewer (`annotation.*.model` in `config.yaml`) and set `LITELLM_BASE_URL` / `LITELLM_API_KEY`.
- Smoke test: `uv run ncse analyse --sample --limit 2`, read the records, then `uv run ncse check analyst --sample`. Check that the service accepts `temperature`/`max_tokens`, whether `response_format: json_object` is supported, and the real token counts.
- Stage 7: pilot on the 24 articles of `corpus_sample/` (both steps, sample mode), then present the reports and a reading of the statements to the owner (✋3), with a cost estimate for the full run from `uv run ncse estimate`.

## Problems and observations

- 2026-11-22: an NCSE entry is a layout box, not an article; the labels are assigned per box and are noisy (D-012).
- *The Leader* exists in two editions (LDR, CLD) with mostly the same text; only LDR is used (D-010).
- The OCR model sometimes invents text (headers with wrong dates, repeated sentences, passages that cannot belong to the issue's date). Boxes that hit the OCR output limit or loop are now left out and listed (D-017). Short invented passages without loops are not caught; watch for them in the pilot.
- Many rebuilt articles were fragments. Review titles in *The Leader* are usually the first words of a text box, not title boxes; with these headings recognised, 3,059 of 4,135 Leader articles are now whole units (D-016). The *Monthly Repository* still has many fragments, because its layout misses headings (417 units over 3 pages).
- 2026-11-22 (second session): owner's answers recorded as D-016 to D-018. No balancing of the two periodicals in the pilot or statistics.
- The *Monthly Repository* gives about 0.5 million words, *The Leader* about 3 million.
- 2026-11-22 (stage 5): longest article ~6,100 words, so one request per article, no splitting. The corpus sample shows many judgements of singers and actors (theatre/music notices) and of non-fiction books; both needed a provisional rule (D-023). Prompt examples are invented, so the corpus sample stays unseen by the prompts and can serve as the pilot. Examples were checked against the schemas and the verbatim rule.
- 2026-11-22 (stage 6): ✋2 approved, including the provisional scope rulings (D-023). Owner asked that both steps be checked for format and instruction adherence; strict rules reject, interpretive ones flag (D-025). Rough input estimate for the full analyst run: 5,375 requests, about 29 million input tokens, of which about 23 million are the instructions repeated in every request (4,300 tokens each); prompt caching by the service, if available, would cut that cost. Output tokens unknown until the pilot.
