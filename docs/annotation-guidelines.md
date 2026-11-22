# Annotation guidelines: evaluative statements about the arts

This document defines **what** is annotated. How certain each annotation is, and how annotations are reviewed, is defined in `evidence-and-review.md`. The two documents are used together.

The guidelines are written for both human and LLM annotators. They are the basis for the analyst's prompt, but the prompt itself is a separate, versioned file.

## 1. What we are looking for

We look for **evaluative statements** in critical texts: passages where the critic, or someone the critic quotes, **judges** the following things as good or bad:

- a **creator**: writer, poet, composer, painter, sculptor, dramatist, etc.;
- a **work**: a book, poem, opera, painting, play, etc.;
- a **kind of work**, such as a genre or school ("modern French novels", "the sensation drama").

### What is not an evaluation

- Neutral description or summary: "The story is set in Devon"; "the volume contains twelve poems".
- Plain facts about publication or performance: "published in three volumes"; "first performed at Covent Garden".
- Judgements about things other than creators and their works, such as political events or the price of a book. Cases at the boundary, like performers, publishers and exhibitions, are listed in `decisions.md` and settled there.

## 2. The unit: one statement

A **statement** is one evaluation of one target on one criterion.

A single passage often contains several statements. Each becomes a separate, identifiable record, and all of them refer to the same passage. For example, "Mr. A.'s poems are graceful, but their tendency is pernicious, and they are far below Mr. B.'s" contains three statements:

1. A's poems: positive, aesthetic value.
2. A's poems: negative, moral value.
3. A's poems compared with B's: negative, link to tradition. This also implies a positive statement about B's poems.

So every statement has its own identifier, and also the identifier of the passage it comes from. This lets users count statements and still see which ones were made together.

## 3. Fields

Each statement has the following fields. The words in italics are suggested field names. The final names are fixed in the data dictionary.

| Field | What to record |
|---|---|
| **Quotation** (*quote*) | The passage containing the statement, **copied exactly from the text**, in full: at least the whole sentence, more if needed to understand the statement. OCR errors are copied as they are. (The checking code tolerates differences that leave the words unchanged, and the dataset stores the exact text of the source; see D-022.) |
| **Creator** (*creator*) | The name of the person judged or whose work is judged, as written in the text (e.g. "Mr. Tennyson", "the author of *Jane Eyre*"). Empty if unknown. |
| **Art** (*art*) | One of: `literature`, `music`, `theatre`, `visual art` (painting, sculpture, engraving, architecture, etc.). If none fits, use `other` and explain in a note; such cases are collected and settled in `decisions.md`. |
| **Work title** (*work_title*) | The title of the work being judged, as written in the text. Empty if the statement is about a creator or a genre in general. |
| **Genre** (*work_genre*) | The kind of work: novel, sonnet, oratorio, farce, portrait, etc. Use the word in the text where there is one. |
| **Evaluative expression** (*evaluative_expression*) | The word or phrase that makes this an evaluation ("tedious", "a noble work", "not without merit"). It must appear inside the quotation, exactly as written. |
| **Polarity** (*polarity*) | `positive` or `negative`: the evaluation the writer **intends**. |
| **Sarcasm** (*sarcastic*) | `yes` if the evaluative words are meant ironically, otherwise `no`. When sarcastic, polarity records the intended meaning: ironic praise is `negative`. |
| **Criterion** (*criterion*) | The ground of the evaluation, one of the five listed in section 4. |
| **Quoted source** (*quoted_source*) | If the evaluation belongs to someone other than the critic (a quoted reviewer, "the public", "a contemporary"), who it is. Empty when the critic speaks in their own voice. |
| **Evidence level and assumptions** | Defined in `evidence-and-review.md`. Every statement carries them. |

**Empty fields.** Leave a field empty when the text gives no basis for it. Do not fill gaps with guesses unless the guess is explicitly marked as a *suggestion*, as `evidence-and-review.md` describes.

**Names and titles.** Record them as written. Normalising them (e.g. matching "Boz" with "Dickens") is a later, separate step.

## 4. Evaluation criteria

| Criterion | The work or creator is judged by… | Typical expressions (illustrations, not a closed list) |
|---|---|---|
| `aesthetic value` | beauty, skill, style, form, power, interest, taste | graceful, vigorous, clumsy, tedious, finely finished |
| `moral value` | moral or religious character, effect on readers or audience | wholesome, elevating, coarse, pernicious, indelicate |
| `usefulness` | instruction, information, practical or educational use | instructive, valuable to the student, of no service |
| `novelty` | originality, freshness, or the lack of them | original, fresh, hackneyed, a mere imitation |
| `tradition` | relation to tradition, established models, the canon, the rules of the art | worthy of Milton, in the spirit of the old masters, defies all rules |

- `novelty` concerns **newness**. `tradition` concerns how the work **stands in relation to an established standard or model**, whether that relation is judged good or bad. When one expression does both, as in "a feeble imitation of Byron", record two statements.
- When an evaluation clearly rests on two criteria, record two statements, one for each.
- When the criterion is not obvious from the words, choose the most plausible one and mark the choice as *inferred*, with the assumption behind it.

## 5. Special cases

- **Mixed judgements** such as "clever but immoral" are split into separate statements. There is no "mixed" or "neutral" polarity.
- **Comparisons** often evaluate two targets at once: one positively, the other negatively, or both on the same scale. Record a statement for each target that is actually judged.
- **Negated and hedged praise.** "Not without merit" is a positive evaluation, often a weak one. Record the polarity. The strength of an evaluation is not annotated.
- **Quoted evaluations.** Record the quoted source. If the critic then agrees or disagrees with the quotation, that is a separate statement in the critic's own voice.
- **Anonymous works.** Leave the creator empty, or record the description used in the text ("the author of *Waverley*").
- **Headings.** In reviews, the title and author of the reviewed book are often given in a heading above the review. Information read from that heading counts as part of the text.

## 6. Illustration

The following passage is **invented** for illustration and is not taken from the corpus:

> "Mr. Hartley's new oratorio, *The Deluge*, is a laborious and tedious performance; we are told by a contemporary that it is 'the finest sacred work of the age,' a judgement in which we cannot concur."

This passage gives three statements:

1. Creator *Mr. Hartley*; work *The Deluge*; genre *oratorio*; art *music*; expression "laborious and tedious"; polarity *negative*; criterion *aesthetic value*; no quoted source.
2. Same work; expression "the finest sacred work of the age"; polarity *positive*; criterion *aesthetic value*; quoted source *a contemporary*.
3. Same work; expression "a judgement in which we cannot concur"; polarity *negative*; criterion *aesthetic value*; no quoted source. The critic rejects the quoted praise.

In all three, the quotation field holds the whole sentence, exactly as written.
