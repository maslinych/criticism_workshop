# Working with the LLM service

Practical lessons for whoever builds the annotation stages (prompts, the scripts that call the LLM, the checks). They come from a test round in which a trial version of the analyst and reviewer steps was run against the university's LiteLLM service, with several models of different sizes, on articles of the corpus sample. The decisions that follow from them are D-022 to D-024 in `docs/decisions.md`; the rules are in `AGENTS.md`.

Numbers below (times, token counts) are what was observed on this service with these articles. They are a guide, not a guarantee: measure again with the models you use.

A few terms:

- A **token** is the unit in which models read and write text, roughly three quarters of an English word. Services count and charge by tokens, and limit answers by tokens.
- A **reasoning model** (also "thinking model") writes out a hidden chain of reasoning before its answer. The reasoning is counted as output tokens and takes time, although it is not part of the answer.
- **Recall** is the share of the real evaluations in an article that the analyst finds; **precision** is the share of its statements that are correct.

## 1. Choosing models

**Try before you choose.** Before the pilot, run both steps on one or two articles of the corpus sample with each candidate model, and read every statement. This costs little and showed more than any description of the models did. Pick test articles that contain the hard cases of the annotation guidelines: a theatre or music notice full of judgements of performers, a review that quotes another critic, an article with irony.

**What to look at, in this order:**

1. **Recall.** Does the analyst find the evaluations of works and creators that a careful reader finds? The reviewer can delete statements but can never add one, so what the analyst misses is lost for good.
2. **Scope.** Does it keep to the rules about what counts (for example, whether judgements of singers and actors count)? Statements outside the rules cost time and money twice: once to write, once for the reviewer to delete.
3. **Format.** Does it return the agreed JSON every time?
4. **Time and tokens** per article (section 3).

**What was observed:**

- **Small models** (around 8 billion parameters) could not do the task. One never produced JSON: it wrote a sentence of commentary and repeated it until the length limit.
- **Mid-sized models without reasoning** returned valid JSON, but ignored the scope rules (most statements in a theatre notice judged the singers), split one sentence into many statements, and "tidied" quotations.
- **Reasoning models** followed the scope rules far better and missed fewer evaluations. They are slower, and most of their output is reasoning: 70–80% of the output tokens in the tests.
- **Turning reasoning off** in a reasoning model made it behave like a model without reasoning: it saved about a quarter of the time on a short article, but found fewer evaluations and added many statements outside the rules.
- Some services offer a **"fast" variant** of a model next to the regular one. In the tests the regular variant thought for so long that the service gave up on long articles (section 4); the fast variant stayed within the limit and gave the best results of the models tried.
- **The reviewer's deletion rate tells you about the analyst.** With a weak analyst, a sound reviewer deleted two thirds of the statements, mostly for good reasons. With a strong analyst, the same reviewer deleted nothing.
- **Analyst and reviewer may be the same model** (`docs/evidence-and-review.md` allows either). The same model may share its own blind spots: in the tests it accepted every statement of a strong analyst, including a few borderline ones. Store the reviewer's reasoning (section 2) and read it in the pilot to see whether it considered the hard cases.

**A model listed by the service is not necessarily one you may use.** The service's list of models (`/models`) showed models that then refused requests with "not authorized" (HTTP 403). Only a real request shows access.

## 2. Settings for every request

- **Ask for JSON through the interface, not only in the prompt.** The OpenAI-compatible interface takes `response_format: {"type": "json_object"}`. With it, models stopped writing text before the JSON. Keep the instruction in the prompt as well, and keep checking the answer in code: some models ignore the setting, and the setting does not check the structure.
- **Use `temperature: 0`, but do not expect repeatable answers.** On a shared service the same request sent again still gives a different answer, and so does its reasoning; adding a fixed `seed` did not change that. Plain evaluations come out the same almost every time, borderline ones vary. Treat the variation as something to measure (D-025, `docs/evidence-and-review.md`, section 8).
- **Set a generous output limit (`max_tokens`).** Answers are longer than one expects: one analyst answer for a 3,000-character article had 30 statements and 8,000 tokens of JSON. For reasoning models the reasoning counts against the same limit: 7,000 to 19,000 reasoning tokens per article were seen, and once the whole limit of 8,000 went on reasoning, leaving an empty answer. 32,000 was enough for every article in the tests. A limit that is too low wastes the whole answer: a cut-off JSON answer cannot be used.
- **Reasoning settings.** The interface has a standard `reasoning_effort` setting (`low`, `medium`, `high`). Models hosted by the service itself may ignore it: in the tests `low` changed nothing. Some models have their own switch (for some, `chat_template_kwargs: {"enable_thinking": false}` turns reasoning off), which the LiteLLM service passes on unchanged. Make such options configurable, check their effect in the reasoning-token count, and compare the statements, not only the time (section 1).
- **Record everything that comes back**: the raw answer, the settings sent, the token counts (the service reports reasoning tokens separately, under `completion_tokens_details`), the model name the service reports, and the model's reasoning text if the service returns it (field `reasoning_content` or `reasoning` of the message). The reasoning is not data, but it is the only way to see why a statement was made, kept or deleted.

## 3. Time and cost

- **Time is roughly the number of output tokens divided by the writing speed.** The speed was steady at about 100 tokens per second per request in the tests, so a reasoning analyst took 1.5 minutes for a 3,000-character article and over 4 minutes for a 10,000-character one. Measure the speed of your model in the smoke test and estimate from it.
- **Output, not input, dominates time.** The instructions are sent with every request (several thousand tokens), which costs money but little time.
- **Several requests at once** (for example four) shorten a run if the service serves them in parallel; check this in a small run.
- **Estimate from the pilot.** Before the pilot, only the input tokens can be counted exactly. Output and reasoning tokens per article come from the pilot, and the cost estimate for the full run (`AGENTS.md`, section 8) should use them.

## 4. Errors and limits of the service

- **The service has a time limit for one answer.** In the tests it was about 300 seconds: after that the service returned a gateway error (HTTP 502) although the model was still working. Retrying such a request is useless: it takes as long and fails the same way. A gateway error or time-out that comes **after a long wait** should mark that article as failed (with the reason) and let the run go on; if several articles in a row fail this way, stop the run, because the model as a whole is too slow. Long articles are at risk: the corpus has several hundred articles over 10,000 characters. Turning reasoning down, a faster model, or receiving the answer piece by piece as it is written ("streaming", not tested here) are possible remedies.
- **"Busy" answers that come quickly** (HTTP 429 "too many requests", 500, 502, 503 and 504) are worth retrying after a pause that grows each time. They are not the model's fault and should not count as attempts.
- **Other refusals stop the run at once**: a wrong key (401), no access to the model (403), an unknown model name (400 or 404). Give a message that says what to check.
- **Stopping by hand must work.** Pressing Ctrl-C should send no new request and end any pause at once. If requests run at the same time in the background, the main program must not wait for them indefinitely: in the tests a run went on for half an hour after Ctrl-C. Answers already being paid for should still be saved if possible; a second Ctrl-C should quit at once.
- **Save each answer as soon as it arrives**, before checking it, so that a crash or interruption never loses a paid answer.

## 5. Checking answers and retrying

The rules are in `AGENTS.md` (section 6) and D-022, D-023. Lessons behind them:

- **Do not reject a whole answer for one bad statement.** A good answer had 30 statements, of which 2 failed a check; rejecting it lost all 30, and the retry cost a full answer. Only an answer that is unusable as a whole (not JSON, cut off, wrong structure) is retried. A passage or statement that fails a check is set aside with its reasons, the rest is kept.
- **Models rarely correct individual statements when told to.** Asked to fix listed problems, one model returned exactly the same answer twice. If an answer is identical to the previous attempt, stop asking.
- **Do not send a huge broken answer back with a retry.** A model caught in a loop wrote 70,000 characters; sending them back with the retry made the next request four times as long, and the model looped again. Send only the beginning of a cut-off answer.
- **Most quotation mismatches are tidying, not invention.** The model dropped a stray full stop where the corpus joins two text boxes ("the Minuet.⏎⏎and Saraband"), joined a word broken at a line end ("appre-elated"), left out a semicolon inside quotation marks, or "corrected" an OCR error. None of these changes a word. The three levels of matching in D-022 accept them, flag the corrected OCR errors, and still reject text that is not in the article.
- **Check loose matches for whole words.** Without that rule, "no ground for supposing" matched "any ground for supposing" with one changed letter, the opposite meaning.
- **Judge a change against the variation between runs.** When a new prompt version or another model gives different results, part of the difference is chance. Before concluding that a change worked, send the same requests more than once with the old version too, and compare the difference with the variation of repeated runs (D-025).
- **Rules about evidence are often broken in small ways**, for example an `observed` value with an assumption added. Count such failures in the pilot before deciding whether to keep rejecting them.
