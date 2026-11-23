# Output format of the annotation stages

**Status: approved at ✋2, 2026-11-22.** Decisions D-022 to D-025 in `decisions.md`. Implemented in `src/ncse/checks.py`.

This document describes exactly what the two LLM steps return, what the checking code does with it, and what the final table will look like. The *content* of the annotation is defined in `annotation-guidelines.md` and `evidence-and-review.md`; this file defines its *form*. The prompts themselves are in `prompts/` (see `prompts/README.md`).

A few terms used below:

- **JSON** is a plain-text format for structured data: lists in `[ ]`, named fields in `{ }`. Both LLM steps answer in JSON, because a program can check it reliably.
- A **schema** is a formal description of what a valid JSON answer looks like: which fields it has and which values they may take. Each prompt version comes with one (`output.schema.json`).
- A **claim** is one filled field of a statement, such as "the creator is Mr. Hartley". Each claim carries an evidence level (`evidence-and-review.md`).

## 1. The flow of one article

1. **Analyst.** The code sends the analyst prompt with the article's text and four metadata items (periodical, issue date, identifier, heading). One request per article, except for long articles (section 1a).
2. **Check.** The code checks the answer (section 3). If the check fails, it asks again (section 6).
3. **Identifiers.** The code numbers passages and statements and records where each quotation sits in the text file (section 4).
4. **Reviewer.** The code sends the reviewer prompt with the same article and the analyst's statements, now carrying identifiers. The reviewer sees only the analyst's output, never any other reasoning.
5. **Check again.** The code checks every reviewer action (section 5.2) and applies the allowed ones.
6. **Assemble.** The results of all articles become the statements table (section 7).

## 1a. Long articles in parts (D-034)

The pilot showed that the model writes about 2.5 tokens of answer (mostly reasoning) per character of article, so an article much longer than about 8,000 characters takes longer than the LLM service allows for one answer, or exceeds the answer's length limit. Such articles are therefore sent in **parts**. The corpus is not changed: the split exists only while the article is processed, and the results are joined back into one result per article.

- **Split.** An article longer than `annotation.max_part_chars` (6,000 characters) is cut into the smallest number of parts within that limit, of roughly equal length, at paragraph breaks, preferably one after the end of a sentence (`src/ncse/parts.py`). The split depends only on the text and the setting.
- **Context.** Each part after the first is sent with context the model must not annotate: the article's first `annotation.context_opening_chars` characters (usually with the heading and the book under review) and the `annotation.context_before_chars` characters just before the part. The prompt versions that allow this have a second user message template, `user-part.md`.
- **Checks.** A quote must match a passage of its own part; a quote copied from the context is set aside as a failed passage. Values marked observed are looked for in the whole article.
- **Records.** Each part has its own record, with all its attempts, in `<step>/parts/<article_id>.part<k>of<n>.json`. When all parts are done, the article's record is written from them: passages and statements are numbered on over the whole article (p01, p02, …; a failed passage keeps its number), positions are counted from the start of the article, every passage and failed item records its `part`, and the result lists the `parts` with their positions. The article's record keeps a summary of the parts' attempts (tokens, errors) and the list of part records. The article is accepted only if every part is; otherwise it is failed, and `--retry-failed` sends only the failed parts again.
- **Reviewer.** The reviewer reviews the same parts, each with the same context and only the statements whose passages come from that part. The actions of all parts are applied together to the article's statements.
- **Re-check.** `ncse check` re-checks every part's record and confirms that joining them gives exactly the article's stored record.

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

A check has one of three outcomes (D-027):

- it **rejects** the whole answer, which is then retried (section 6);
- it **sets aside** one passage or statement as a *failed item*: the item is kept in the record with its reasons, but it does not enter the data, and the rest of the answer is accepted without a retry;
- it **flags** a statement or passage: the item is kept, and the flag goes into the table and the report.

**Rejected (the whole answer):**

1. **Instruction adherence** (D-025): the answer is empty; is not a bare JSON object (text before or after it, or Markdown code fences); gives a key twice in one object; or was cut off because it reached the length limit.
2. The answer is not valid JSON, or does not match the schema: missing or extra fields, values outside the allowed lists, wrong types.

**Set aside (one passage, with all its statements):**

3. A `quote` cannot be found in the article's text file. The matching (D-028) tries three levels and records which one succeeded:
   - *exact*: the same characters; runs of spaces, tabs and line breaks count as one space, and spaces at the start and end are ignored;
   - *normalised*: the same letters and digits in the same order, ignoring all other characters and capital letters. This tolerates differences in punctuation, the form of quotation marks and dashes, line breaks, words broken by a hyphen at a line end, and capitals, as long as the words stay the same;
   - *approximate*: as *normalised*, but a few letters or digits may differ, as when the model corrects an OCR error ("patricians" for "patriicians") or makes a typo. At most `quotes.max_char_errors` (3) may differ, and at most `quotes.max_error_share` (5%) of the letters and digits of the quote, so a phrase under 20 letters must match without any error. The passage is accepted and flagged (item 14).

   A normalised or approximate match must begin and end at word boundaries in the text, so that a changed letter cannot turn "any ground" into "no ground". Whatever the level, the code records the exact text of the article that the quote matched (`quote_source`); this, not the model's copy, is the quotation in the data.

**Set aside (one statement):**

4. An `evaluative_expression` cannot be found inside the source text of its quote, with the same three levels (item 15 flags approximate ones). The exact source text of the expression is recorded.
5. An `inferred` or `suggested` claim has no assumption, or an `observed` claim has one.
6. A statement has none of `creator`, `work_title`, `work_genre` (no target).
7. `art` is `other` and `note` is empty, or `note` is an empty text (it must be `null` or say something).
8. A name, title, genre or quoted source has spaces at its start or end, or is wrapped as a whole in quotation marks or underscores (the prompt asks to leave them out; a closing mark that is part of the name, as in `the Author of “Waverley.”`, is fine).

Failed items keep their numbers: if passage `p03` is set aside, the next accepted passage is still `p04`, so every item can be traced back to the raw answer.

**Flagged:**

9. **Observed but not found.** A free-text claim (`creator`, `work_title`, `work_genre`, `quoted_source`) marked `observed` whose value does not occur anywhere in the article text, at the *normalised* level (letters and digits only, capitals ignored). This catches, for example, a name the model has silently corrected or completed. (It cannot be checked for `art`, `polarity`, `sarcastic` and `criterion`, whose values are categories, not words of the text.)
10. **Repeated quote.** Two passages with the same quotation.
11. **Repeated statement.** Two statements identical in every field.
12. **Passage order.** A passage that lies earlier in the article than the one before it (the prompt asks for article order).
13. **Ambiguous quote.** A quotation that occurs more than once in the article. The first occurrence is recorded.
14. **Approximate quote.** A quotation that matched with a few changed characters (item 3). The detail gives the number of characters and the source text.
15. **Approximate expression.** The same for an evaluative expression.

## 4. What the code adds

The LLM never numbers, counts or locates anything (`AGENTS.md`, section 5). The code adds:

| Item | Example | How it is made |
|---|---|---|
| `passage_id` | `LDR-1852-12-11-003-p02` | article identifier + passage number, in the order of the analyst's answer |
| `statement_id` | `LDR-1852-12-11-003-p02-s01` | passage identifier + statement number within the passage |
| `quote_start`, `quote_end` | `1234`, `1410` | position of the quotation in the text file, in characters from the start |
| `part` | `2` | for a long article sent in parts (section 1a): the part the passage came from |
| `quote_source`, `evaluative_expression_source` | | the exact text of the article at that position (D-028) |
| `quote_match`, `quote_char_errors`, `expression_match` | `normalised`, `0` | how the model's copy matched the text: `exact`, `normalised` or `approximate`, and how many characters differ |
| failed items | | passages and statements set aside, with the reasons and what the model wrote (section 3) |
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

1. it is empty, not a bare JSON object, gives a key twice, was cut off, is not valid JSON, or does not match the schema (the same adherence checks as for the analyst);
2. an action names a statement that does not exist, or a field that is empty (`null`);
3. an action is not allowed on its field (table above);
4. a downgrade does not lower the level: the new level must be below the current one (`observed` > `inferred` > `suggested`);
5. `delete` comes with a level, or `downgrade` without one;
6. the reason is empty or only spaces;
7. two actions concern the same field of the same statement, or a deleted statement has further actions.

Then the code applies the actions. Deleted statements and fields **stay in the data**, marked as deleted with the reason. The statement's level is recomputed from the claims that remain.

## 6. Failures and retries

- When an answer is rejected, the code logs every failed check and asks again, at most `annotation.max_retries` times (`config.yaml`). The new request repeats the original one and adds a short message listing the failed checks (for example "quote of passage 3 not found in the article"), so that the model can correct itself. If the answer was cut off at the length limit, only its beginning is sent back (`annotation.retry_echo_chars`, D-026).
- If the service gives up on a request after a long wait (the model needs longer than it allows), that article (or part of an article) is marked failed at once and the run goes on; several in a row stop the run (D-029, D-031).
- If the model returns exactly the same answer as in the previous attempt, no further attempt is made: the article is marked failed at once (D-027).
- If the answer still fails after the last retry, the article is marked **failed** for that step, with the reasons. It appears in the stage report and in a list of failed articles; it is never dropped silently. Failed articles are not sent to the reviewer.
- Only problems with the whole answer lead to a retry. Failed passages and statements (section 3) are set aside without a retry (D-027): asking again costs a full answer, and in the smoke tests the model did not correct such items when asked. Each failed item is kept in the record with its reasons and listed in the stage report; it is never dropped silently. The reviewer sees only the accepted statements.
- Every answer, accepted or not, is stored. A run that is interrupted continues with the articles that have no accepted answer yet; paid requests are never repeated.

## 7. The final statements table (draft)

`statements.csv`, one row per statement, deleted statements included. Failed items (section 3) are not statements of the dataset; they are listed separately, with their reasons. The final column names and descriptions are fixed in the data dictionary at stage 8; this is the intended shape.

- **Identity and source:** `statement_id`, `passage_id`, `article_id`, `periodical`, `issue_date`, `quote` (the exact source text, `quote_source`), `quote_start`, `quote_end`, `quote_match`, `evaluative_expression` (exact source text).
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
