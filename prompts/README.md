# Prompts

The texts sent to the language model. They are part of the code (`AGENTS.md`, section 2): kept here as separate files, under version control, and never written into the scripts.

| Folder | Step |
|---|---|
| `analyst/v1/` | The analyst: finds evaluative statements in one article |
| `reviewer/v1/` | The reviewer: may only delete statements or fields, or lower evidence levels |

Each version folder holds three files:

- `system.md`: the instructions. They are sent unchanged with every request. Their content is derived from `docs/annotation-guidelines.md` and `docs/evidence-and-review.md`, plus the provisional scope rulings of D-023.
- `user.md`: the message for one article. Names in double braces, such as `{{text}}`, are filled in by the code: `{{periodical}}`, `{{issue_date}}`, `{{article_id}}`, `{{heading}}` (from `metadata.csv`), `{{text}}` (the article's text file, unchanged), and for the reviewer `{{statements_json}}` (the analyst's checked statements with their short identifiers).
- `output.schema.json`: the JSON schema the answer must match. The format is explained in plain language in `docs/output-format.md`.

**Versions.** The version used is set in `config.yaml` (`annotation`) and recorded with every annotation. A version may still be edited until it is first used in a paid run; after that it is frozen, and any change becomes a new folder (`v2`, …) with an entry in `docs/decisions.md`. Changing an approved prompt needs the project owner's approval.

**Status:** `v1` is a draft awaiting approval (✋2).
