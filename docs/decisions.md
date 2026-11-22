# Decision log

This file records the decisions made in the project and why they were made. That includes general design choices and small rulings on particular annotation cases. Add new entries at the end and never delete old ones. If a decision is changed, add a new entry that refers to the old one.

**Entry format**

- **ID and title**
- **Date**
- **Status:** adopted / provisional / replaced by D-xxx
- **Decision:** what was decided
- **Reason:** why
- **Consequences:** what changes in the code, the prompts or the data

---

## Decisions taken in the project brief

**D-001 — Source and periodicals**
Status: adopted. The source is NCSE v2.0, and the periodicals are *The Monthly Repository* and *The Leader*. Reason: the edition is openly licensed (CC BY 4.0), split into units and labelled by topic, and these two periodicals carry the most literary and art criticism.

**D-002 — Initial selection rule**
Status: provisional until the data has been inspected. Select entries with text type *article* and topic *Arts, culture, entertainment and media*. Reason: this is the simplest rule using the existing labels. Its accuracy is checked in stage 2 (see `README.md`).

**D-003 — Unit of annotation: one statement = one target × one criterion × one polarity**
Status: adopted. Reason: this lets several judgements in one passage be counted separately while staying linked through a shared passage identifier.

**D-004 — Evidence levels are assigned per claim (field); the statement takes the lowest level**
Status: adopted, open to revision by the project owner. Reason: within one statement, different fields often rest on different kinds of evidence. For example, the title may be stated while the criterion is inferred. Per-field levels let the reviewer act precisely, and the statement-level summary keeps filtering simple.

**D-005 — The reviewer may only delete or downgrade, always with a reason; deleted items are kept and marked**
Status: adopted. Reason: see `evidence-and-review.md`, section 5. Requiring a reason for downgrades as well as deletions makes the review step open to inspection.

**D-006 — Source text is never corrected; quotations reproduce OCR errors**
Status: adopted. Reason: quotations are checked by code against the source text, and corrections would break traceability.

## Open questions for the project owner

These should be settled during or after the pilot, then recorded as decisions.

- **Q-1. Performers.** Do evaluations of actors, singers and musicians count as evaluations of "creators"?
- **Q-2. Other targets.** How are evaluations of exhibitions, theatres, concerts as events, editions and translations treated?
- **Q-3. The `other` category for art.** Opera could count as music or theatre, and book illustration as literature or visual art. Which rules apply to such boundary cases, and does `other` stay as a category?
- **Q-4. Selection beyond the topic label.** Should texts labelled with other topics (e.g. *Religion*, *Education*) that contain reviews be added? If so, how are they identified?
- **Q-5. Quotation matching tolerances.** Which trivial differences may the quotation check ignore, beyond whitespace and line breaks?
