# Output format of the annotation stages

**Status: draft for approval (✋2), 2026-11-22.** Decisions D-022 to D-024 in `decisions.md`.

This document describes exactly what the two LLM steps return, what the checking code does with it, and what the final table will look like. The *content* of the annotation is defined in `annotation-guidelines.md` and `evidence-and-review.md`; this file defines its *form*. The prompts themselves are in `prompts/` (see `prompts/README.md`).

A few terms used below:

- **JSON** is a plain-text format for structured data: lists in `[ ]`, named fields in `{ }`. Both LLM steps answer in JSON, because a program can check it reliably.
- A **schema** is a formal description of what a valid JSON answer looks like: which fields it has and which values they may take. Each prompt version comes with one (`output.schema.json`).
- A **claim** is one filled field of a statement, such as "the creator is Mr. Hartley". Each claim carries an evidence level (`evidence-and-review.md`).

## 1. The flow of one article

1. **Analyst.** The code sends the analyst prompt with the article's text and four metadata items (periodical, issue date, identifier, heading). One request per article: the longest article in the corpus has about 6,100 words, which fits easily into one request.
2. **Check.** The code checks the answer (section 3). If the check fails, it asks again (section 6).
3. **Identifiers.** The code numbers passages and statements and records where each quotation sits in the text file (section 4).
4. **Reviewer.** The code sends the reviewer prompt with the same article and the analyst's statements, now carrying identifiers. The reviewer sees only the analyst's output, never any other reasoning.
5. **Check again.** The code checks every reviewer action (section 5.2) and applies the allowed ones.
6. **Assemble.** The results of all articles become the statements table (section 7).

The raw text of every LLM answer is stored unchanged, together with the request, so that every processed result can be compared with what the model actually returned.

## 2. The analyst's answer

One JSON object with a list of **passages**. Each passage has a verbatim **quote** and a list of the **statements** that rest on it. The structure makes the passage identifier of D-003 explicit: statements in one passage share it.

```
{"passages": [
  {"quote": "...",
   "statements": [
     {"evaluative_expression": "...",
      "creator":       {"value": "...", "evidence": "observed", "assumption": null},
      "art":           {"value": "music", "evidence": "observed", "assumption": null},
      "work_title":    null,
      "work_genre":    {...},
      "polarity":      {...},
      "sarcastic":     {...},
      "criterion":     {"value": "aesthetic value", "evidence": "inferred", "assumption": "..."},
      "quoted_source": null,
      "note": null}
   ]}
]}
```

| Field | Kind | May be empty? | Allowed values |
|---|---|---|---|
| `quote` | verbatim text | no | a continuous passage of the article text |
| `evaluative_expression` | verbatim text | no | a continuous part of `quote` |
| `creator` | claim | yes | free text, as written in the source |
| `art` | claim | no | `literature`, `music`, `theatre`, `visual art`, `other` |
| `work_title` | claim | yes | free text, as written |
| `work_genre` | claim | yes | free text, as written where possible |
| `polarity` | claim | no | `positive`, `negative` |
| `sarcastic` | claim | no | `yes`, `no` |
| `criterion` | claim | no | `aesthetic value`, `moral value`, `usefulness`, `novelty`, `tradition` |
| `quoted_source` | claim | yes; empty = the critic's own voice | free text, as written |
| `note` | remark | yes; required when `art` is `other` | free text |

A **claim** is written as `{"value": ..., "evidence": ..., "assumption": ...}`:

- `evidence` is `observed`, `inferred` or `suggested`;
- `assumption` is a short text for `inferred` and `suggested`, and `null` for `observed`.

An **empty field** is `null` as a whole. It is not a claim and has no evidence level.

**Verbatim fields have no level of their own.** `quote` and `evaluative_expression` are copied from the text and checked by code, so they are `observed` by definition (D-024). The code records them as `observed`.

An article without evaluations gives `{"passages": []}`. This is a valid, expected answer, and it is recorded, so the article is not sent again.

## 3. What the code checks in the analyst's answer

A check either **rejects** the answer (it is retried, section 6) or **flags** a statement (the statement is kept, and the flag goes into the table and the report).

**Rejected:**

1. The answer is not valid JSON, or does not match the schema: missing or extra fields, values outside the allowed lists, wrong types.
2. A `quote` is not a passage of the article's text file. The comparison ignores only differences in **whitespace**: runs of spaces, tabs and line breaks count as one space, and spaces at the start and end are ignored (D-022). Every other difference, including curly versus straight quotation marks, is a mismatch (open question Q-5).
3. An `evaluative_expression` does not occur inside its `quote`, with the same tolerance.
4. An `inferred` or `suggested` claim has no assumption, or an `observed` claim has one.
5. A statement has none of `creator`, `work_title`, `work_genre` (no target).
6. `art` is `other` and `note` is empty.

**Flagged:**

7. **Observed but not found.** A free-text claim (`creator`, `work_title`, `work_genre`, `quoted_source`) marked `observed` whose value does not occur anywhere in the article text, ignoring whitespace and capital letters. This catches, for example, a name the model has silently corrected or completed. (It cannot be checked for `art`, `polarity`, `sarcastic` and `criterion`, whose values are categories, not words of the text.)
8. **Repeated quote.** Two passages with the same quotation.
9. **Ambiguous quote.** A quotation that occurs more than once in the article. The first occurrence is recorded.

## 4. What the code adds

The LLM never numbers, counts or locates anything (`AGENTS.md`, section 5). The code adds:

| Item | Example | How it is made |
|---|---|---|
| `passage_id` | `LDR-1852-12-11-003-p02` | article identifier + passage number, in the order of the analyst's answer |
| `statement_id` | `LDR-1852-12-11-003-p02-s01` | passage identifier + statement number within the passage |
| `quote_start`, `quote_end` | `1234`, `1410` | position of the quotation in the text file, in characters from the start |
| statement evidence level | `inferred` | the lowest level among the statement's claims (D-004) |
| run information | | corpus version, model, model settings, prompt version, date and time of the request, numbers of tokens |

In the messages to the reviewer, statements are named by the short form (`p02-s01`), which is easier for the model to copy; the code adds the article identifier.

## 5. The reviewer's answer

### 5.1 Format

The reviewer receives the article and the analyst's passages and statements in the same form as in section 2, with the short identifiers added. It answers with a list of **actions**; it never repeats or rewrites the statements. Anything the reviewer does not mention stays as it is.

```
{"actions": [
  {"statement_id": "p01-s02", "field": "statement", "action": "delete",
   "new_evidence": null, "reason": "..."},
  {"statement_id": "p03-s01", "field": "work_genre", "action": "downgrade",
   "new_evidence": "inferred", "reason": "..."}
]}
```

| Field | Allowed values |
|---|---|
| `statement_id` | an identifier from the input, e.g. `p01-s02` |
| `field` | `statement` (the whole statement), or one of the claim fields |
| `action` | `delete` or `downgrade` |
| `new_evidence` | for `downgrade`: `inferred` or `suggested`; for `delete`: `null` |
| `reason` | free text, required |

Because the reviewer can only name an action, not write a new value, the format itself makes adding or rewriting impossible. The code then checks the rest.

**Which actions are allowed on which field** (D-024):

| Field | delete | downgrade |
|---|---|---|
| whole statement | yes | no |
| `creator`, `work_title`, `work_genre` | yes | yes |
| `art`, `polarity`, `sarcastic`, `criterion`, `quoted_source` | no: delete the statement instead | yes |
| `quote`, `evaluative_expression` | no: delete the statement instead | no |
| `note` | no | no |

Why can `polarity` and the other four not be deleted on their own? A statement without a polarity, criterion or art is no longer a complete evaluation; and deleting `quoted_source` would silently turn someone else's opinion into the critic's own, which is a change of value, not a removal. If one of these is wrong, the statement as a whole is wrong and is deleted.

### 5.2 What the code checks in the reviewer's answer

The answer is **rejected** (and retried) if:

1. it is not valid JSON or does not match the schema;
2. an action names a statement that does not exist, or a field that is empty (`null`);
3. an action is not allowed on its field (table above);
4. a downgrade does not lower the level: the new level must be below the current one (`observed` > `inferred` > `suggested`);
5. `delete` comes with a level, or `downgrade` without one;
6. the reason is empty;
7. two actions concern the same field of the same statement, or a deleted statement has further actions.

Then the code applies the actions. Deleted statements and fields **stay in the data**, marked as deleted with the reason. The statement's level is recomputed from the claims that remain.

## 6. Failures and retries

- When an answer is rejected, the code logs every failed check and asks again, at most `annotation.max_retries` times (`config.yaml`). The new request repeats the original one and adds a short message listing the failed checks (for example "quote of passage 3 not found in the article"), so that the model can correct itself.
- If the answer still fails after the last retry, the article is marked **failed** for that step, with the reasons. It appears in the stage report and in a list of failed items; it is never dropped silently. Failed articles are not sent to the reviewer.
- A whole answer is accepted or rejected as a unit. Accepting the good statements of a partly bad answer would make the result depend on the order of checks and hide failures; whether to allow it can be decided after the pilot.
- Every answer, accepted or not, is stored. A run that is interrupted continues with the articles that have no accepted answer yet; paid requests are never repeated.

## 7. The final statements table (draft)

`statements.csv`, one row per statement, deleted statements included. The final column names and descriptions are fixed in the data dictionary at stage 8; this is the intended shape.

- **Identity and source:** `statement_id`, `passage_id`, `article_id`, `periodical`, `issue_date`, `quote`, `quote_start`, `quote_end`, `evaluative_expression`.
- **For each claim field** (`creator`, `art`, `work_title`, `work_genre`, `polarity`, `sarcastic`, `criterion`, `quoted_source`), five columns, for example for `creator`:
  - `creator`: the value;
  - `creator_evidence`: the level after review;
  - `creator_assumption`: the analyst's assumption;
  - `creator_review`: `deleted`, `downgraded` or empty;
  - `creator_review_reason`.

  The analyst's original level can be read from the level after review and the review action; it is also kept as `creator_evidence_analyst`.
- **Statement level:** `evidence` (lowest level among the claims left after review), `deleted` (`yes`/`no`), `deleted_reason`, `note`, `flags` (from section 3).
- **Provenance:** `corpus_version`, `analyst_model`, `analyst_prompt_version`, `analyst_run_at`, `reviewer_model`, `reviewer_prompt_version`, `reviewer_run_at`. Model settings are in a separate runs table, referred to by a run identifier.

The values of deleted fields stay in their columns, so that the review step can be studied; users who want only accepted data filter on the `_review` and `deleted` columns.

## 8. Worked example

The prompts contain invented examples: `prompts/analyst/v1/system.md`, section 8, gives a complete analyst answer, and `prompts/reviewer/v1/system.md`, section 4, a reviewer answer. For the analyst example the code would produce:

| statement_id (short) | expression | polarity | criterion | quoted_source | statement level |
|---|---|---|---|---|---|
| p01-s01 | laborious and tedious | negative | aesthetic value | | observed |
| p01-s02 | the finest sacred work of the age | positive | aesthetic value | a contemporary | observed |
| p01-s03 | a judgement in which we cannot concur | negative | aesthetic value | | inferred |
| p02-s01 | a more edifying production | negative | aesthetic value | | inferred |
