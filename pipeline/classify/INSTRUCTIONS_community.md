# Classification task (community-sourced videos): is this PsychTube material, and where does it go?

You are labeling YouTube videos for **PsychTube**, a curated video library for people who want to learn
psychology, neuroscience, mental health and the science of human behavior. These videos were linked by
people in psychology communities (Reddit psych subreddits, Psychology & Neuroscience Stack Exchange).
People link all kinds of things, so many rows are NOT psychology content (music, memes, unrelated news,
self-promotion, pseudoscience). Your job is to decide, for every row, whether it belongs and which topics it fits.

## Input

A JSONL file. Each line has: `vid`, `title`, `channel`, `duration_s`, `views`, `yt_category`,
`yt_keywords`, `description` (first 300 chars of the YouTube description) and `contexts`: up to 3 of
the community posts/comments that linked it (`kind`, `score`, `question`/`thread`/`subreddit`, `snippet`).
The context tells you *why* someone linked it: as a recommendation, as an example of something, as a
question ("is this video right?"), or as a joke.

Read the whole file with the Read tool. Do not write code to classify; judge each row yourself.

## Output

Write a JSONL file (path given below) with exactly one line per input row, same order, this shape:

```json
{"vid": "...", "keep": true, "topics": ["memory", "learning-studying"], "cw": [], "contested": "", "contested_role": "", "course": false, "confidence": 0.9}
```

- `keep` (bool): true if a psychology student or enthusiast would expect this video in a psychology
  video library. The video's **primary subject** must be psychology, neuroscience, mental health,
  psychiatry, cognition, emotion, consciousness/philosophy of mind, human or animal behavior, child
  development, or "the psychology of X". Lectures, talks, documentaries, explainers, interviews,
  classic experiment footage (e.g. the still-face experiment, Milgram footage, Piaget conservation tasks),
  therapy demonstrations and first-person accounts of mental illness all count.
  - KEEP even if short, old or low-production, as long as it is substantive psychology.
  - KEEP pseudoscience *only if* it is a famous case people discuss critically (then also tag
    `contested`/`pseudoscience-skepticism`); DROP ordinary self-help, motivational, "manifestation",
    astrology, MBTI-typing entertainment, and spiritual channels presenting claims as psychology.
  - DROP music videos, movie/TV clips used as jokes, news without a psychological lens, politics,
    fitness/nutrition without brain/mind content, programming, pure philosophy or religion, personal
    vlogs, ASMR, product ads, and anything you cannot tell is about psychology from title +
    description + context.
  - When the context is a question ("does this video's claim hold up?") the video can still be kept
    if it is a substantive psychology video; judge the video, not the asker.
- `topics`: 1–3 topic ids from TAXONOMY.md, best fit first. Empty list if `keep` is false.
- `cw`: content-warning ids that apply (suicide/self-harm, eating disorders, sexual content,
  abuse/violence, substance use) — only when the video substantially covers them. Usually `[]`.
- `contested`: a contested-finding id from TAXONOMY.md if the video **presents that finding as
  established fact** OR is **a critique** of it. Otherwise `""`.
- `contested_role`: `"promotes"` or `"critique"` when `contested` is set, else `""`.
- `course`: true if the video is one lecture of a university course or a numbered lecture series.
- `confidence`: 0–1, your confidence in the `keep` decision.

Be decisive and consistent. Use only topic ids that exist in TAXONOMY.md. Output nothing but the
file; when done, reply with one line: how many rows you kept out of how many.
