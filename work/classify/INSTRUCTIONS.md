# Classification task: is this video PsychTube material, and where does it go?

You are labeling candidate YouTube videos for **PsychTube**, a curated video library for people who
want to learn psychology, neuroscience, mental health and the science of human behavior, built from
videos that online communities (Hacker News, Reddit psych subreddits, Psychology Stack Exchange) have
recommended to each other. These candidates came from a loose keyword prefilter over HackerTube's
export, so many are NOT psychology at all. Your job is to decide, for every row, whether it belongs and
which topics it fits.

## Input

A JSONL file. Each line has: `vid`, `title`, `channel`, `content_type`, `primary_topic`, `tags`,
`hn_categories` (HackerTube's own categories), `summary`, `why_hn`, `hn_score`, `prefilter`
(`core` = HackerTube filed it under a psychology/neuro/mental-health/consciousness category;
`adj+kw` / `kw` = only matched keywords).

Read the whole file with the Read tool. Do not write code to classify; judge each row yourself.

## Output

Write a JSONL file (path given below) with exactly one line per input row, same order, this shape:

```json
{"vid": "...", "keep": true, "topics": ["memory", "learning-studying"], "cw": [], "contested": "", "contested_role": "", "course": false, "confidence": 0.9}
```

- `keep` (bool): true if a psychology student or enthusiast would expect this video in a psychology
  video library. The video's **primary subject** must be psychology, neuroscience, mental health,
  psychiatry, cognition, emotion, consciousness/philosophy of mind, human or animal behavior, child
  development, or "the psychology of X" (e.g. the psychology of persuasion, of games, of money).
  Also keep famous psych-adjacent works that psych people recommend (e.g. *The Century of the Self*,
  Sapolsky's lectures, Randy Pausch only if framed around psychology — it is not, so drop it).
  - KEEP: behavioral economics (Kahneman, Ariely, Thaler, nudges, incentives on human behavior),
    learning science and study techniques, sleep science, meditation research, addiction, parenting
    grounded in psychology, animal cognition, linguistics only when about language acquisition or
    language and thought, philosophy only when about mind/consciousness/free will/moral psychology,
    productivity only when it is really about attention, motivation, habits or procrastination
    research, education only when about how people learn, management only when it is about human
    motivation/behavior (e.g. RSA Animate "Drive"), design/games only when the video is about the
    psychology of users/players, persuasion/propaganda/cults, crime and deception psychology.
  - DROP: programming, math, physics, hardware, business strategy, politics and history without a
    psychological lens, comedy and music clips (even if about emotions), general documentaries,
    tool/productivity-app tips, nutrition and fitness unless about the brain/mind, AI/LLM talks unless
    they are about cognition or consciousness, "how to be a better engineer" talks that merely mention
    cognitive load, news.
  - When in doubt for a `core` row, lean keep. When in doubt for a `kw` row, lean drop.
- `topics`: 1–3 topic ids from TAXONOMY.md, best fit first. Empty list if `keep` is false.
- `cw`: content-warning ids that apply (suicide/self-harm, eating disorders, sexual content,
  abuse/violence, substance use) — only when the video substantially covers them. Usually `[]`.
- `contested`: a contested-finding id from TAXONOMY.md if the video **presents that finding as
  established fact** (e.g. Amy Cuddy's power-posing TED talk → `power-posing`; a Stanford Prison
  Experiment documentary → `stanford-prison`) OR if the video is **a critique** of it. Otherwise `""`.
- `contested_role`: `"promotes"` or `"critique"` when `contested` is set, else `""`.
- `course`: true if the video is one lecture of a university course or a numbered lecture series
  (e.g. "1. Introduction to Human Behavioral Biology", "Lecture 7: ...", "Psych 1 - Lecture 3").
- `confidence`: 0–1, your confidence in the `keep` decision.

Be decisive and consistent. Use only topic ids that exist in TAXONOMY.md. Output nothing but the
file; when done, reply with one line: how many rows you kept out of how many.
