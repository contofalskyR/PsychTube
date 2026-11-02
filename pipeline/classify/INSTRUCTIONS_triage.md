# Playlist triage: which candidate playlists belong in PsychTube's institutional tier?

PsychTube's institutional tier carries complete courses and lecture collections that **universities,
their faculty, research institutes, scientific societies and clinical institutions** published on
YouTube. A sweep of ~400 institutional channels and ~100 topic searches produced candidate playlists.
You decide, from the card alone, which ones to pull in full.

## Input

A JSONL file, one playlist per line: `pid`, `title` (playlist title), `channel`, `channel_verified`,
`count` (videos), `source` (`sweep` = found on a channel we already judged institutional; `search` =
found by a topic search, so the channel still needs judging), `queries` (search terms that found it,
when any), and sometimes `channel_desc`.

Read the whole file with the Read tool. Judge each row yourself; do not write code to classify.

## Output

A JSONL file (path given below), exactly one line per input row, same order:

```json
{"pid": "...", "keep": true, "inst": "University of Toronto", "kind": "course", "english": true, "confidence": 0.85, "why": "PSY 2xx lecture recordings on the professor's own channel"}
```

- `keep`: true when ALL of these hold:
  1. **Institutional publisher.** The channel is a university, a department/school/lab/centre of one,
     an OpenCourseWare / NPTEL / national open-education outlet, a research institute (NIH, Allen,
     Max Planck, Santa Fe…), a scientific or professional society (APA, APS, SfN, RCPsych, BPS…), a
     teaching hospital / psychiatry department, or **an identifiable academic's own channel carrying
     their own course lectures** (a channel named after a person whose playlists are course codes or
     "Lecture N" series counts; a channel named after a person that only re-uploads other people's
     lectures does not).
     NOT kept: students' or fans' re-uploads of Yale/Stanford/MIT/Sapolsky/Peterson/Bloom lectures
     (those are already in from the source), exam-prep and coaching channels (UGC NET, CUET, UPSC,
     CSS/PMS, MCAT, EPPP, NCLEX, A-level/GCSE/AP revision), nursing/medical cram channels, YouTuber
     explainer channels (CrashCourse, Khan Academy, Professor Dave, Psych2Go, Sprouts…), commercial
     course sellers, podcasts, and personal channels of practitioners without an academic course.
  2. **Subject.** Psychology, neuroscience, psychiatry, cognitive science, philosophy of mind,
     behavioral economics, child development, linguistics *of the mind* (psycholinguistics), animal
     behavior, mental health. Not general biology, medicine, education policy, sociology, marketing,
     machine learning, or campus life.
  3. **Form.** Lectures, a taught course, a seminar/colloquium/grand-rounds series, or a themed
     collection of talks. Not promos, shorts, trailers, news clips, student testimonials, "day in
     the life", commencement, or how-to-apply videos. `count` ≥ 3.
  4. **English** (set `english` false and `keep` false otherwise; Indian NPTEL courses are in English).
- `inst`: the institution to credit, in its common English name ("MIT", "University of Oxford",
  "IIT Kanpur (NPTEL)", "NIH / NIMH", "Royal College of Psychiatrists"). For a professor's own
  channel, their university if evident from the title/description, else "Independent lecturer".
- `kind`: `course` (one taught course, lectures in order), `series` (a named lecture series, one
  theme), `talks` (a collection of separate talks, seminars or grand rounds).
- `confidence`: 0–1 on the keep decision.
- `why`: ≤ 12 words.

When the card is ambiguous but the channel is clearly institutional and the title is clearly a
psychology course, keep it (confidence ≤ 0.6); the next stage sees the actual lectures and can
still drop it. When the channel is a person you cannot place and the playlist title is just a
subject word ("Psychology", "Neuroscience"), drop it. Output nothing but the file; when done, reply
with one line: kept out of total.
