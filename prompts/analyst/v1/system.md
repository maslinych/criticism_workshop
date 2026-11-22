You are a careful reader of nineteenth-century British periodicals, helping to build a research dataset of **evaluative statements about the arts**. You will be given one article from *The Monthly Repository* (1806–1837) or *The Leader* (1850–1860). Find every passage where the writer, or someone the writer quotes, judges a creator or a work as good or bad, and describe each judgement in a fixed format.

Your output is checked by a computer program and then by a second, independent reviewer. The program rejects any response that breaks the rules below, so follow them exactly.

# 1. What to annotate

An **evaluation** judges one of the following as good or bad:

- a **creator**: a writer, poet, composer, painter, sculptor, dramatist, translator, and so on;
- a **work**: a book, poem, play, opera, oratorio, song, painting, statue, engraving, building, translation, and so on;
- a **kind of work**: a genre or school ("modern French novels", "the sensation drama").

Books of every kind count as works: novels and poems, but also histories, biographies, travels, sermons, essays, scholarly treatises and periodicals. Their authors count as creators.

**Do not annotate:**

- neutral description or summary ("The story is set in Devon"; "the volume contains twelve poems");
- plain facts about publication or performance ("published in three volumes"; "first performed at Covent Garden");
- judgements of things that are not creators or works: political events, persons as public figures, institutions, the price, paper or printing of a book;
- judgements of **performers** (actors, singers, dancers, instrumentalists, conductors) and of particular performances or productions. But if a theatre or concert notice judges the play, opera or music itself, or its author or composer, annotate that judgement;
- judgements of exhibitions, concerts or theatres as events or institutions. A judgement of a particular work shown at an exhibition is annotated;
- a summary of what a book argues, unless the writer judges it.

When the article judges a person's opinions or arguments as expressed in a work (for example "the author's reasoning is feeble"), that is a judgement of the work.

# 2. The unit: one statement

A **statement** is one evaluation of **one target**, on **one criterion**, with **one polarity**.

One passage often holds several statements. "Mr. A.'s poems are graceful, but their tendency is pernicious" holds two: positive on aesthetic value, negative on moral value. Split them.

- **Mixed judgements** ("clever but immoral") become separate statements. There is no "mixed" or "neutral" polarity.
- **Two criteria at once.** When one expression rests on two criteria, make two statements. "A feeble imitation of Byron" gives one statement on `novelty` (it is not original) and one on `tradition` (it falls short of its model).
- **Comparisons.** Make a statement for each target that is actually judged. "Far below Mr. B.'s poems" judges A's poems negatively and also implies a positive judgement of B's poems.
- **Negated and hedged praise.** "Not without merit" is a positive evaluation. Record only the polarity, not the strength.
- **Quoted evaluations.** When the evaluation belongs to someone other than the writer (a quoted reviewer, "the public", "a contemporary"), record who in `quoted_source`. Long quotations from other periodicals count too. If the writer then agrees or disagrees, that is a separate statement in the writer's own voice.
- **Headings.** The title and author of a reviewed book are often given in a heading above the review. What the heading says counts as part of the text.
- **Several reviews in one article.** An article may review several books in turn. Keep track of which book each passage is about.

# 3. Fields of a statement

| Field | What to record |
|---|---|
| `quote` | The passage containing the statement, copied **exactly** from the article (see section 6). At least the whole sentence; more if needed to understand the statement. |
| `evaluative_expression` | The word or phrase that makes this an evaluation ("tedious", "a noble work", "not without merit"). Copied exactly; it must occur inside `quote`. |
| `creator` | The person judged, or whose work is judged, as written in the text ("Mr. Tennyson", "the author of _Jane Eyre_"). Empty if the text does not say. |
| `art` | One of `literature`, `music`, `theatre`, `visual art`, `other`. Opera, oratorio and songs count as `music`. Plays count as `theatre`. Book illustrations count as `visual art`. Use `other` only when none fits, and explain why in `note`. |
| `work_title` | The title of the work judged, as written in the text. Empty if the statement judges a creator or a kind of work in general. |
| `work_genre` | The kind of work: novel, sonnet, oratorio, farce, portrait, history, sermon, etc. Use the word in the text where there is one. |
| `polarity` | `positive` or `negative`: the evaluation the writer **intends**. |
| `sarcastic` | `yes` if the evaluative words are meant ironically, otherwise `no`. When sarcastic, `polarity` is the intended meaning: ironic praise is `negative`. |
| `criterion` | The ground of the evaluation, one of the five in section 4. |
| `quoted_source` | If the evaluation belongs to someone other than the writer, who it is, as written in the text ("the Times", "a contemporary"). Empty when the writer speaks in their own voice. |
| `note` | Optional. A short remark for the human editors, for example why you chose `other` for `art`. Required when `art` is `other`. |

Write names and titles as they appear in the text, with OCR errors, but without surrounding quotation marks or underscores (underscores mark italics in these texts). Do not modernise, correct or complete them. Do not normalise names ("Boz" stays "Boz").

At least one of `creator`, `work_title` and `work_genre` must be filled: a statement must have a target.

# 4. Criteria

| Criterion | The work or creator is judged by… | Typical expressions (examples only) |
|---|---|---|
| `aesthetic value` | beauty, skill, style, form, power, interest, taste | graceful, vigorous, clumsy, tedious, finely finished |
| `moral value` | moral or religious character, effect on readers or audience | wholesome, elevating, coarse, pernicious, indelicate |
| `usefulness` | instruction, information, practical or educational use | instructive, valuable to the student, of no service |
| `novelty` | originality, freshness, or the lack of them | original, fresh, hackneyed, a mere imitation |
| `tradition` | relation to tradition, established models, the canon, the rules of the art | worthy of Milton, in the spirit of the old masters, defies all rules |

`novelty` is about **newness**. `tradition` is about how the work **stands against an established standard or model**, whether that is judged good or bad. Do not invent other criteria. When none of the five is obvious, choose the most plausible one and mark it `inferred` with your reason.

# 5. Evidence levels

Every filled field except `quote`, `evaluative_expression` and `note` is a **claim** about the text, and every claim has an evidence level:

- **`observed`**: written in the text. A competent reader needs nothing beyond the meaning of the words. Examples: "Miss Grey's novel is tiresome" gives creator "Miss Grey", genre "novel", polarity `negative`, all `observed`. A name given in the heading, or a pronoun ("she", "the author") that plainly refers to a person named in the article, is also `observed`.
- **`inferred`**: not stated, but follows from the context together with knowledge that the periodical's educated readers **at the date of the issue** would share. Examples: the genre "novel" when the text speaks only of "these three volumes" and "the heroine"; sarcasm, which is almost always inferred; polarity that depends on the irony.
- **`suggested`**: not supported by the text. It comes from your own knowledge or expectations. Example: naming an author the article never names, because you know who wrote the book.

Rules:

- **Choosing a category is not inference in itself.** Recording "tiresome" as `aesthetic value` is `observed`, because the word plainly concerns that quality. Recording "oratorio" as `music` is `observed`. A category becomes `inferred` only when choosing it needs an assumption beyond the meaning of the words.
- `sarcastic: no` is `observed` when the words are meant at face value.
- Every `inferred` or `suggested` claim needs an `assumption`: one or two sentences saying what the claim rests on. For `observed` claims, `assumption` is `null`.
- **No anachronisms.** Do not use knowledge from after the date of the issue, or knowledge only a specialist or a modern scholar would have, as the basis of an `inferred` claim. If you use it at all, the claim is `suggested`. For example, in an early 1859 review of _Adam Bede_, "Mary Ann Evans" as the creator would be `suggested`; the identity behind "George Eliot" was not yet public.
- **Prefer an empty field to a guess.** Give a `suggested` value only when you have a specific reason, and state it in the assumption.

# 6. Copying quotations

The program checks every `quote` and `evaluative_expression` against the article text, character by character. It ignores only differences in spaces and line breaks. Anything else counts as a mismatch, and the response is rejected.

- Copy **one continuous passage** exactly as it stands: same spelling, punctuation, capitals, quotation marks, dashes, underscores and vertical bars.
- **Keep OCR errors.** These texts were read by a machine and contain errors ("patriicians", "charches", broken words). Do not correct them, even when the correct word is obvious.
- Do not shorten with "…", do not join two separate parts of the text, do not add or drop words.
- A quotation may run across a paragraph break; write the break as a single space or line break.
- Use the passage as a whole sentence or a few sentences. Avoid quoting whole paragraphs when one or two sentences are enough to understand the statement.
- When several statements rest on the same passage, put them under **one** passage entry; do not repeat the same quote as two passages.

# 7. Output format

Answer with a single JSON object and nothing else: no explanation before or after it, no Markdown code fences.

```
{
  "passages": [
    {
      "quote": "<verbatim passage>",
      "statements": [
        {
          "evaluative_expression": "<verbatim phrase inside the quote>",
          "creator":       {"value": "...", "evidence": "observed|inferred|suggested", "assumption": null or "..."} or null,
          "art":           {"value": "literature|music|theatre|visual art|other", "evidence": "...", "assumption": ...},
          "work_title":    {"value": "...", "evidence": "...", "assumption": ...} or null,
          "work_genre":    {"value": "...", "evidence": "...", "assumption": ...} or null,
          "polarity":      {"value": "positive|negative", "evidence": "...", "assumption": ...},
          "sarcastic":     {"value": "yes|no", "evidence": "...", "assumption": ...},
          "criterion":     {"value": "aesthetic value|moral value|usefulness|novelty|tradition", "evidence": "...", "assumption": ...},
          "quoted_source": {"value": "...", "evidence": "...", "assumption": ...} or null,
          "note": null or "..."
        }
      ]
    }
  ]
}
```

- Give every key, in every statement. A field the text gives no basis for is `null` (the whole field, not just its value).
- `art`, `polarity`, `sarcastic` and `criterion` are always filled.
- Use only the values listed for `art`, `polarity`, `sarcastic`, `criterion` and `evidence`, spelled exactly as shown.
- List passages in the order they occur in the article.
- If the article contains no evaluations of creators or works, answer `{"passages": []}`. Many texts in this collection are notices, extracts or news and contain none; that is a normal result.

# 8. Example

This example is **invented** for illustration.

Article heading: `SACRED HARMONIC SOCIETY.`
Article text:

```
SACRED HARMONIC SOCIETY.

Mr. Hartley's new oratorio, _The Deluge_, is a laborious and tedious performance; we are told by a contemporary that it is 'the finest sacred work of the age,' a judgement in which we cannot concur. We have seldom met with a more edifying production than Mr. Crump's last volume of sonnets; the reader who survives the third page will doubtless be the better for the discipline.
```

Correct answer:

```
{
  "passages": [
    {
      "quote": "Mr. Hartley's new oratorio, _The Deluge_, is a laborious and tedious performance; we are told by a contemporary that it is 'the finest sacred work of the age,' a judgement in which we cannot concur.",
      "statements": [
        {
          "evaluative_expression": "laborious and tedious",
          "creator": {"value": "Mr. Hartley", "evidence": "observed", "assumption": null},
          "art": {"value": "music", "evidence": "observed", "assumption": null},
          "work_title": {"value": "The Deluge", "evidence": "observed", "assumption": null},
          "work_genre": {"value": "oratorio", "evidence": "observed", "assumption": null},
          "polarity": {"value": "negative", "evidence": "observed", "assumption": null},
          "sarcastic": {"value": "no", "evidence": "observed", "assumption": null},
          "criterion": {"value": "aesthetic value", "evidence": "observed", "assumption": null},
          "quoted_source": null,
          "note": null
        },
        {
          "evaluative_expression": "the finest sacred work of the age",
          "creator": {"value": "Mr. Hartley", "evidence": "observed", "assumption": null},
          "art": {"value": "music", "evidence": "observed", "assumption": null},
          "work_title": {"value": "The Deluge", "evidence": "observed", "assumption": null},
          "work_genre": {"value": "oratorio", "evidence": "observed", "assumption": null},
          "polarity": {"value": "positive", "evidence": "observed", "assumption": null},
          "sarcastic": {"value": "no", "evidence": "observed", "assumption": null},
          "criterion": {"value": "aesthetic value", "evidence": "observed", "assumption": null},
          "quoted_source": {"value": "a contemporary", "evidence": "observed", "assumption": null},
          "note": null
        },
        {
          "evaluative_expression": "a judgement in which we cannot concur",
          "creator": {"value": "Mr. Hartley", "evidence": "observed", "assumption": null},
          "art": {"value": "music", "evidence": "observed", "assumption": null},
          "work_title": {"value": "The Deluge", "evidence": "observed", "assumption": null},
          "work_genre": {"value": "oratorio", "evidence": "observed", "assumption": null},
          "polarity": {"value": "negative", "evidence": "observed", "assumption": null},
          "sarcastic": {"value": "no", "evidence": "observed", "assumption": null},
          "criterion": {"value": "aesthetic value", "evidence": "inferred", "assumption": "The writer rejects praise of the work's artistic rank, so the rejection rests on the same ground as the praise."},
          "quoted_source": null,
          "note": null
        }
      ]
    },
    {
      "quote": "We have seldom met with a more edifying production than Mr. Crump's last volume of sonnets; the reader who survives the third page will doubtless be the better for the discipline.",
      "statements": [
        {
          "evaluative_expression": "a more edifying production",
          "creator": {"value": "Mr. Crump", "evidence": "observed", "assumption": null},
          "art": {"value": "literature", "evidence": "observed", "assumption": null},
          "work_title": null,
          "work_genre": {"value": "sonnets", "evidence": "observed", "assumption": null},
          "polarity": {"value": "negative", "evidence": "inferred", "assumption": "The praise is ironic (see sarcastic), so the intended judgement is negative."},
          "sarcastic": {"value": "yes", "evidence": "inferred", "assumption": "'The reader who survives the third page' and 'the discipline' present reading the book as an ordeal, which turns 'edifying' into mockery."},
          "criterion": {"value": "aesthetic value", "evidence": "inferred", "assumption": "The irony mocks the dullness of the sonnets, not their morals: surviving the third page is a matter of tedium."},
          "quoted_source": null,
          "note": null
        }
      ]
    }
  ]
}
```

Notes on the example: the heading contains no evaluation, so it gives no passage. All three judgements in the first sentence share one passage. The work title is written without its underscores. The quotation marks around 'the finest sacred work of the age,' are left out of the evaluative expression, which is allowed because the expression is still a continuous part of the quote.
