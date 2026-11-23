# Prompts

The texts sent to the language model. They are part of the code (`AGENTS.md`, section 2): kept here as separate files, under version control, and never written into the scripts.

| Folder | Step |
|---|---|
| `analyst/v1/` | The analyst: finds evaluative statements in one article |
| `analyst/v2/` | v1 plus a section on long articles sent in parts, and `user-part.md` (D-034) |
| `reviewer/v1/` | The reviewer: may only delete statements or fields, or lower evidence levels (used in the pilot) |
| `reviewer/v2/` | The same, stricter: deletes or downgrades when in doubt (D-033) |

Each version folder holds three files, four from v2:

- `system.md`: the instructions. They are sent unchanged with every request. Their content is derived from `docs/annotation-guidelines.md` and `docs/evidence-and-review.md`, plus the provisional scope rulings of D-023.
- `user.md`: the message for one article. Names in double braces, such as `{{text}}`, are filled in by the code: `{{periodical}}`, `{{issue_date}}`, `{{article_id}}`, `{{heading}}` (from `metadata.csv`), `{{text}}` (the article's text file, unchanged), and for the reviewer `{{statements_json}}` (the analyst's checked statements with their short identifiers).
- `user-part.md` (from v2): the message for one part of a long article, with context before it (D-034). `{{text}}` is then the part; `{{context}}`, `{{part_number}}` and `{{part_count}}` are filled in as well, and for the reviewer `{{statements_json}}` holds only the statements of that part.
- `output.schema.json`: the JSON schema the answer must match. The format is explained in plain language in `docs/output-format.md`.

**Versions.** The version used is set in `config.yaml` (`annotation`) and recorded with every annotation, together with the SHA-256 checksum of the instructions, so answers to different texts of the same version can always be told apart. A version may still be edited until it is used in the pilot run; after that it is frozen, and any change becomes a new folder (`v2`, …) with an entry in `docs/decisions.md`. Short smoke tests before the pilot do not freeze a version (D-027). Changing an approved prompt needs the project owner's approval.

**Status:** `v1` was approved at ✋2 (2026-11-22) and used in the pilot. `reviewer/v2` (D-033) replaced the reviewer's v1 after the pilot, at the owner's request. Its sentences on how the program treats rule-breaking answers were changed with the owner's approval after the smoke tests (D-027).
