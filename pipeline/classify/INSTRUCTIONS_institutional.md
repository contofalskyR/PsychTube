# Classification task (institutional videos): file each lecture under PsychTube's topics

You are labeling YouTube videos for **PsychTube**, a curated video library for people who want to learn
psychology, neuroscience, mental health and the science of human behavior. These videos come from the
**institutional tier**: playlists published by universities, their faculty, or long-standing scientific
institutions (MIT OpenCourseWare, Yale Courses, NPTEL/IIT, Gresham College, the Royal Institution, a
professor's own channel …). Unlike community-sourced videos they are presumed relevant: your main job is
to assign **topics**, and to drop the few videos that are not psychology/neuroscience/mind/behavior at all.

## Input

A JSONL file. Each line has: `vid`, `title`, `channel`, `playlist` (the course or collection title),
`institution`, `position` ("12/24" = 12th of 24 videos), `duration_s`, `yt_category`, `yt_keywords`,
`description` (first 300 chars of the YouTube description).

Read the whole file with the Read tool. Do not write code to classify; judge each row yourself.
Titles like "PSY409_Lecture07" carry no information: label those by the playlist (the course) alone.

## Output

Write a JSONL file (path given below) with exactly one line per input row, same order, this shape:

```json
{"vid": "...", "keep": true, "topics": ["memory", "learning-studying"], "cw": [], "contested": "", "contested_role": "", "course": true, "confidence": 0.9}
```

- `keep` (bool): true unless the video is clearly **not** about psychology, neuroscience, psychiatry,
  cognition, emotion, consciousness/philosophy of mind, human or animal behavior, child development,
  behavioral economics, or the methods used to study them (statistics for the behavioral sciences
  counts). Keep course housekeeping videos only if they contain teaching ("Syllabus" lectures that
  introduce the field: keep; a 2-minute "how to submit assignments": drop). Drop videos from a mixed
  institutional playlist that are about physics, chemistry, administration, fundraising, campus
  tours, or pure molecular/cellular biology with no link to behavior or mind. Drop podcast-style
  celebrity interviews that happen to sit in a professor's playlist. When unsure, keep.
- `topics`: 1–3 topic ids from TAXONOMY.md, best fit first. Use the **lecture's own subject** when
  the title or description gives one (lecture 7 of an intro course on "Memory" → `memory`), and the
  course's subject when the title is uninformative. Empty list if `keep` is false.
- `cw`: content-warning ids that apply (suicide/self-harm, eating disorders, sexual content,
  abuse/violence, substance use) — only when the video substantially covers them. Usually `[]`.
- `contested`: a contested-finding id from TAXONOMY.md if the video **presents that finding as
  established fact** OR is **a critique** of it (lectures on ego depletion, power posing, the Stanford
  prison experiment, learning styles, 10,000 hours, left/right brain, etc.). Otherwise `""`. Lectures that
  *teach* a classic finding while noting its problems count as `critique`.
- `contested_role`: `"promotes"` or `"critique"` when `contested` is set, else `""`.
- `course`: true if the video is one lecture of a taught course or an ordered lecture series; false for
  a standalone talk, seminar or interview.
- `confidence`: 0–1, your confidence in the `keep` decision.

Be decisive and consistent. Use only topic ids that exist in TAXONOMY.md. Output nothing but the
file; when done, reply with one line: how many rows you kept out of how many.
