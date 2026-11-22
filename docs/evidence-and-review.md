# Evidence levels and the analyst–reviewer protocol

This document defines **how sure** we are about each annotation and **how annotations are checked**. It applies to any annotation task. In this project, the things annotated are the evaluative statements defined in `annotation-guidelines.md`.

## 1. Why evidence levels?

A language model, like a human reader, does not only report what a text says. It also fills gaps from context, and from its own general expectations about what texts like this usually contain. These are three very different kinds of knowledge, and the dataset must keep them apart. Users of the data can then decide what to trust, for example by counting only what the texts actually say.

## 2. The three levels

| Level | Meaning | Example (invented review of a novel) |
|---|---|---|
| **observed** | Written directly in the text. A competent reader needs nothing beyond the meaning of the words. | "Miss Grey's novel is tiresome": negative evaluation of Miss Grey's novel. |
| **inferred** | Not stated, but follows from the context together with general knowledge and assumptions that the text's intended readers would share. | The genre "novel" when the text speaks only of "these three volumes" and "the heroine". Sarcasm, which is almost always inferred. |
| **suggested** | Not supported by the text at all. It comes from the model's own expectations about what such texts usually contain. | Naming an author the review never names, because the model "knows" who wrote the book. |

**Assigning categories is not inference in itself.** Recording "tiresome" as `aesthetic value` is observed, because the word plainly concerns that quality. A criterion becomes inferred only when choosing it requires an assumption beyond the meaning of the words.

## 3. Claims and their levels

The analyst's output consists of **claims about the text**. In practice, each filled field of a statement is a claim: "the creator is Miss Grey", "the polarity is negative", "the criterion is moral value", and so on.

- **Every claim gets an evidence level.**
- **Every claim at the level `inferred` or `suggested`** comes with a short statement of the **assumptions** it rests on.
- **The quotation** is always taken verbatim from the text, so it is `observed` by definition. It is the textual basis for all the other claims about the statement.
- **The statement as a whole** takes the **lowest** level among its claims. This makes it easy to filter whole statements while keeping the detail.

## 4. The analyst

The analyst is the first LLM step. For each unit of text, it:

1. Finds the evaluative statements, following `annotation-guidelines.md`.
2. For each statement, gives:
   - the verbatim quotation on which it is based;
   - every field, with its evidence level;
   - the assumptions behind every `inferred` or `suggested` claim.

## 5. The reviewer

The reviewer is a **separate** LLM step. It sees the source text and the analyst's output. It must not see the analyst's reasoning beyond what is written in the output. A different model may be used, and the choice is recorded.

**The reviewer may do only two things.**

1. **Delete** a claim or a whole statement, marking it `DELETED`, with a short reason: why the evidence is insufficient, with reference to the criteria in section 6.
2. **Downgrade** a claim's evidence level, with a short reason:
   - `observed` → `inferred`
   - `inferred` → `suggested`
   - `observed` → `suggested` (two levels at once)

**The reviewer may not do anything else.** In particular, it may not:

- add new statements or claims;
- change any value (a polarity, a name, a criterion);
- rewrite quotations or assumptions;
- raise an evidence level.

These limits are enforced by code (see `AGENTS.md`, section 6). Deleted statements are kept in the data, marked as deleted, so that the reviewer's decisions can be studied.

Why such a narrow role? A reviewer that may only **remove or weaken** claims cannot introduce new errors of its own. Its work is easy to check, and its effect on the data is easy to measure.

## 6. The reviewer's criteria

Besides checking that the quotation really supports each claim, the reviewer applies two criteria to the knowledge and assumptions used.

**Historicity: no anachronisms.** Contextual knowledge and values must not come from a time later than the source.

- **Example.** A review of *Adam Bede* written in early 1859 should not be annotated as naming Mary Ann Evans as the author. Her identity behind the pseudonym "George Eliot" was not publicly known when the review appeared.
- **Example.** A modern view of a writer's reputation, such as "a canonical Victorian novelist", must not be used to interpret what a critic of the 1830s meant.

**Relevance: available to the intended readers.** An assumption must be one that the text's intended audience could readily make. Here, that means educated readers of the periodical at the time of publication. Knowledge that only a specialist, or a modern scholar, would have is not a valid basis for an `inferred` claim.

A claim that fails one of these criteria is **downgraded** to `suggested`, or **deleted** when nothing in the text supports it.

## 7. Summary for users of the data

| You want… | Use |
|---|---|
| only what the texts say | statements whose overall level is `observed`, not deleted |
| a reader's understanding in context | `observed` + `inferred` |
| to study the model's own expectations | `suggested` claims and their assumptions |
| to study the review step | deleted and downgraded claims with their reasons |
