# Course labeling task: describe each university playlist for PsychTube's Courses hub

PsychTube is a curated video library for people who want to learn psychology, neuroscience, mental
health and the science of behavior. Besides community-vouched videos it carries an **institutional
tier**: complete courses and lecture collections that universities, their faculty, or long-standing
scientific institutions published on YouTube. You are writing the catalog card for each playlist.

## Input

`work/inst/courses_in.jsonl`, one JSON object per playlist: `pid`, `inst` (the institution we credit),
`kind` (our guess: `course` = one taught course in lecture order, `series` = a named lecture series by
one speaker or theme, `talks` = a collection of separate talks), `playlist_title`, `channel` (the
YouTube channel that published it), `n_videos`, `description`, `sample_titles` (first 10 video
titles), `typical_length_min`.

Read the whole file with the Read tool. Judge each row yourself; do not write code to do it.

## Output

`work/inst/course_labels.jsonl`, exactly one line per input row, same order:

```json
{"pid": "...", "keep": true, "name": "9.00SC Introduction to Psychology", "lecturer": "John Gabrieli", "year": 2011,
 "kind": "course", "level": "intro", "topics": ["history-of-psychology", "how-the-brain-works"],
 "note": "MIT's full introductory psychology course: 24 lectures from perception to social psychology, taught by John Gabrieli.",
 "per_video_topics": true}
```

- `keep`: false only if the playlist is not psychology / neuroscience / mind / behavior / mental
  health at all (e.g. a university's generic events playlist). Clinical psychiatry, cognitive
  science, behavioral economics, social neuroscience, philosophy of mind, animal behavior and
  positive psychology all count. Keep course playlists whose video titles are only numbers
  (`PSY409_Lecture01`) if the course itself is psychology.
- `name`: the display name. Strip channel noise, dates and emoji; keep course codes when they are
  meaningful ("MIT 9.13 The Human Brain", "Yale PSYC 110: Introduction to Psychology", "Personality
  and Its Transformations"). Do not repeat the institution if it is already in `inst`, except as part
  of a well-known course code (MIT 9.13, Yale PSYC 110).
- `lecturer`: the main lecturer's name if it is evident from the title, description or channel
  (channel named after a person; "with Paul Bloom"; description naming a professor). Empty string if
  unknown or if it is a many-speaker collection.
- `year`: the year the course was taught/recorded if evident (course code suffixes like "Fall 2011",
  "2009", "Jan 2023"); else null.
- `kind`: `course` (one taught course, lectures in order), `series` (a lecture series on one theme,
  usually one speaker, watchable in order but not a degree course), or `talks` (independent talks /
  seminars / interviews collected under a theme). Override the input guess when the titles say otherwise.
- `level`: `intro` (no prerequisites, first course), `advanced` (assumes a first course, graduate or
  research seminar), or `public` (public lectures / outreach for a general audience).
- `topics`: 1–3 topic ids from TAXONOMY.md describing the playlist as a whole, best fit first.
- `note`: one sentence, ≤ 160 characters, written for the card: what the course covers and who
  teaches it. Plain, specific, no marketing words.
- `per_video_topics`: true when the videos span several topics (an intro course, a mixed talk
  series), false when every video is about the same narrow topic (a 40-lecture course on Bayesian
  statistics; three psychiatry lectures on one theme).

Use only topic ids that exist in TAXONOMY.md. Output nothing but the file; when done, reply with
one line: how many rows you kept out of how many.
