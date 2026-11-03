# PsychTube

The psychology videos that psychology people keep telling each other to watch — a static,
account-free video site built from community vouches (Hacker News via HackerTube's export,
psychology subreddits via the Arctic Shift archive, and Psychology & Neuroscience Stack Exchange),
with the receipts on every card and "handle with care" notes on findings that didn't hold up —
plus an **institutional tier**: complete psychology courses that universities, their lecturers and
scientific institutions published publicly — on YouTube (MIT OpenCourseWare, Yale Courses, Stanford,
the IITs via NPTEL, Gresham College, the Royal Institution, professors' own channels…), on a
university's own Panopto (Steven Pinker's Harvard courses) and on the Internet Archive (UC Berkeley's
webcast courses) — every lecture in order, marked "published by" instead of a vouch count.

Institutions also publish single lectures outside any playlist — a named lecture, a grand-rounds
recording, a society's prize lecture — and those come in as **standalone talks** (`raw/institutional/loose.json`):
the same institutional vouch, marked "standalone talk" instead of "lecture 7 of 24". Clinical
neuropsychology is covered this way as well as through courses: KnowNeuropsychology's didactic series,
the British Neuropsychological Society, UCSF's Memory and Aging Center, the aphasia research centres,
and a hundred-odd university and hospital lectures on the syndromes themselves.

Long-form content (over 25 minutes) is ordered by legitimacy before popularity: an institution's own
course or lecture series (or a shelf copy, or a long video on one of the institutions' own channels)
first, the institutions' seminars and conference talks second, fireside chats and interviews third,
podcasts last, with the community score deciding within each tier. Short pieces — demos, clips, TED
talks — are not penalised, and the canon stays a pure count of recommenders.

Provenance is checked **video by video**: a lecture is credited to an institution only when it sits on
one of the institution's own channels, so a TED talk or a CrashCourse clip re-listed in a department's
playlist is not the department's lecture, and a playlist that is mostly other channels' videos is a
watch list, not a publication. Courses on a lecturer's own channel say so, name the lecturer and their
affiliation, and say whether an institutional page confirms it; the unconfirmed ones rank with
independent talks. An external review in November 2026 (`review/REVIEW.md`) drove this and a round of
other fixes, recorded in `pipeline/NOTES.md`.

The Courses hub has two shelves: **taught courses and lecture series** (a full term as the institution
published it), and **seminars & conferences** — research seminar series, hospital grand rounds and the
sessions of annual meetings, which are institutional but not a course and not peer-reviewed, and are
labelled that way on every card and watch page.

Three curated shelves sit beside the catalog, each item with the paper it belongs to (DOIs verified
against Crossref) and a note on whose copy it is: **Primary sources** (the original films of the classic
experiments and case studies, from the archives that hold them: Pavlov's laboratory, Gesell, Skinner's
pigeons, the 1964 split-brain film, the Stanford prison experiment footage, Robbers Cave, the Gloria
films, H.M., Clive Wearing…), **Try it yourself** (demonstrations that work on the viewer: the gorilla,
McGurk, the rubber hand, the hollow mask, Stroop, binocular rivalry…) and **Therapy in practice**
(psychotherapy as it is done: Judith Beck's full CBT sessions, Nottingham's simulated psychiatric
interviews, Yale's motivational interviewing, Mick Cooper's person-centred sessions, and all three
Shostrom "Three Approaches to Psychotherapy" series — Rogers, Perls, Ellis in 1965; Rogers, Shostrom,
Lazarus in 1977; Beck, Strupp, Meichenbaum in 1986 — from the Internet Archive). Experiments with no
authorized copy online (Little Albert, Harlow, Asch, Milgram, the Bobo doll…) are listed with their
paper and no player rather than with a bootleg. A fourth shelf, **Clinical cases on film**, is the
neuropsychology textbook on video: Broca's, Wernicke's and conduction aphasia, hemispatial neglect,
face blindness (the 60 Minutes report with Oliver Sacks and Chuck Close), patient TN's blindsight
corridor from de Gelder's own lab, the Riddoch phenomenon, alien hand, Ramachandran's phantom limbs
and Capgras cases, deep brain stimulation switched off and on, locked-in communication, a
hemispherectomy twelve years on, patient SM's missing amygdala, Phineas Gage's skull at Harvard, two
1950s–60s aphasia films from the Internet Archive, and Helen Keller on a 1928 newsreel.

Every contested finding carries a **replication status** — replicated, smaller than claimed, mixed,
did not replicate, overstated, misreported, myth, fraud/retraction, reversed — with the replication or
review papers it rests on; 67 findings, from power posing, ego depletion and the retracted honesty-pledge
study to the McGurk effect and Stroop (which hold up). The "Replication notes" page groups them by
status (the home row is still "Handle with care"), and a video's watch page
says whether it presents the finding, pushes back on it, or *is* the original footage.

For people who want a prerequisite chain rather than a catalog, a quiet **Pathways** page (linked from
the Courses hub, and from each course that sits on one) gives nine suggested orders through the
courses — from zero to the brain, clinical psychology, clinical neuropsychology, cognitive science,
computational neuroscience, methods and the replication crisis, social and personality, consciousness,
development — each ending in the primary sources and the seminar series where the field talks to
itself. They live in `pipeline/pathways.json` and resolve against whatever courses the build has.

The home page also has a one-line **"Teach me something I don't know"**: open it, pick your background (cognitive
science, neuroscience, clinical, social, philosophy, machine learning…) with no account, and it picks
a vouched talk, a first lecture of a course and a primary source from outside the areas you already
know — different ones each day, never something you've watched.

Lecturers can **list their own course**: a short GitHub issue form (linked from the Courses hub) takes the
public playlist, the institution, a faculty page and the syllabus and reading links; the course then gets
the same page as any other — lectures in order, materials linked, "submitted by the lecturer". Nothing is
uploaded or hosted.

The live site also keeps a **lecture tracker** in the browser: where you stopped in each lecture,
which lectures of a course you've finished, "continue watching" and "your courses" on the home page,
and an up-next panel when a lecture ends. Nothing leaves the browser; Settings → Export moves it.

Built in the spirit of Andrej Karpathy's [HackerTube](https://hackertube.org).

## Run it

**Live site:** https://contofalskyr.github.io/PsychTube/ — videos play in the page there (YouTube's
player refuses to run inside a page opened from disk, which is why the single-file copy links out).

The site is plain HTML/CSS/JS with the catalog baked into `site/data.js`:

- **Quickest:** double-click `serve.command` (macOS) or run `python3 -m http.server 8000 --directory site`,
  then open http://localhost:8000. (Opening `site/index.html` directly from Finder also works for
  browsing; some YouTube embeds refuse to play from a `file://` page, so prefer the local server.)
- **Host it:** upload the `site/` folder anywhere static — Cloudflare Pages, Netlify, GitHub Pages,
  an S3 bucket, a VPS with nginx. No build step, no server code. This repo deploys `site/` to GitHub
  Pages on every push to `main` (`.github/workflows/pages.yml`).

## Layout

```
site/                  the website (index.html, app.js, styles.css, data.js)
site/data/             the export: psychtube.json + DATA.md (give these to your agent)
site/hosted/           the variant published as a claude.ai artifact (no embeds allowed there, so it
                       carries its own thumbnails and links out to YouTube); built by build_artifact.py
pipeline/              scripts that build data.js
  taxonomy.json        52 topics in 9 areas + 67 contested findings (status + verified sources) + content-note ids
  shelves.json         the curated shelves (primary sources, demos, therapy, clinical cases): video, uploader, legitimacy, paper, status
  pathways.json        the Pathways page: ordered routes through the courses, by series id
  triage_overrides.json publishers and playlists dropped after triage, institution renames, affiliated
                       channels (which channels count as an institution's own), playlist re-credits
  institutions.json    raw institution label -> canonical publisher + unit, and the chip short names
  publishers.json      the publisher check: who is behind each personal or name-only channel, their
                       affiliation, whether an institutional page confirms it (ok=false -> unverified)
  merge_pulled.py      appends pulled playlists to raw/institutional/courses.json after triage
  build_catalog.py     merges every source, scores, groups series, writes site/data.js
  make_inst_batches.py writes the labeling inputs for university playlists (course cards + per-lecture topics)
  make_taxonomy_md.py  regenerates classify/TAXONOMY.md from taxonomy.json (run after editing a topic or finding)
  intake_submission.py turns a "Submit a course" GitHub issue into raw/institutional/submissions/issue-<n>.json
  replication_candidates.py keyword pass over the built catalog for replication-badge candidates
  assemble_candidates.py turns the channel/topic sweep (raw/sweep/) into triage batches (work/triage/)
  build_artifact.py    writes site/hosted/ from site/ + raw/youtube/thumbs_*.json
  overrides.json       manual label corrections applied on top of the LLM labels
  NOTES.md             how each source was pulled, scoring details, how to redo it
  classify/            the instructions Claude followed to screen videos and assign topics
  fetch_youtube_meta.py  (optional) refresh YouTube metadata with a Data API key
  reddit_crawler.py    (optional) pull more Reddit vouches from Arctic Shift on an open network
raw/                   compact source data: HackerTube rows for kept videos, Stack Exchange posts,
                       Reddit records, YouTube metadata snapshots, university playlists (raw/institutional/),
                       the institutional channel/playlist sweep (raw/sweep/), Internet Archive course
                       metadata (raw/archive/)
work/                  intermediate files (classification batches and outputs; work/inst/ for the courses,
                       work/triage/ for the sweep's keep/drop decisions, work/replication/ for the
                       replication-status tags)
```

## Rebuild the catalog

```
python3 pipeline/build_catalog.py
```

reads everything under `raw/` and `work/` and rewrites `site/data.js` and `site/data/psychtube.json`.
It is deterministic given the inputs (set `SOURCE_DATE_EPOCH` to pin the `generated` stamp as well), so
re-running it after adding raw data is safe.

### Add more Reddit vouches

`pipeline/reddit_crawler.py` pages through the Arctic Shift API for a list of subreddits and writes
`raw/reddit/reddit_<timestamp>.json`. The archive rate-limits aggressively (expect "Timeout. Maybe
slow down a bit" responses; the script backs off and resumes). New videos then need labels: create
batches with `pipeline/make_batches.py` and have Claude (or any model) fill them in following
`work/classify_new/INSTRUCTIONS.md`, then rebuild.

### Add a university course

Append the playlist to `raw/institutional/courses.json` (`pid`, `inst`, `kind`, and the items as the
other entries have them; `pipeline/NOTES.md` shows the innertube calls that list a playlist, or use
the Data API's `playlistItems`), then `python3 pipeline/make_inst_batches.py --only-mixed` (without the flag it
also queues the lectures of single-topic courses that inherit their course's topics), label the new rows
with `pipeline/classify/INSTRUCTIONS_courses.md` and `INSTRUCTIONS_institutional.md`, and rebuild.
Keep to official channels and lecturers' own channels; mirrors get taken down.

Provenance is per video: the build credits an item to the institution only when it sits on one of the
institution's own channels (a channel that owns a kept playlist or standalone talk, or one listed under
`affiliated_channels` in `pipeline/triage_overrides.json`, keyed by the canonical name in
`pipeline/institutions.json`). After a build, `work/inst/crosschannel.json` lists what was not credited,
most items first; when a channel there is the institution's own (a medical school's CME channel, the
university's TV service), add its id to `affiliated_channels` and rebuild. A playlist that is mostly other
channels' videos is treated as a watch list. If the playlist is on a person's own channel, add the
channel to `pipeline/publishers.json` (`pipeline/classify/INSTRUCTIONS_publishers.md` says what to
check): the collection then shows the lecturer and their affiliation, and ranks with the institutions
only when an institutional page confirms it (`verified: true`, `ok: true`).

A course that is not on YouTube gets `"provider": "panopto"` (with `"host"`) or `"provider": "archive"`
(with each item's `file`); `pipeline/NOTES.md` has the calls that list a Panopto folder or an Internet
Archive item. A course that an institution uploaded as loose videos rather than a playlist (NYU's
*Brain and Behavior*, UCD's *Clinical Neurology* series) gets an invented `pid` (`nyu:brain-and-behavior`,
`ucd:clinical-neurology`), the items in syllabus order and a `url` pointing at the channel search that
lists them.

### Process a submitted course

Lecturers and institutions can list a course themselves through the "Submit a course" issue form
(`.github/ISSUE_TEMPLATE/submit-course.yml`; linked from the Courses hub and the About page). To
process issue N: `python3 pipeline/intake_submission.py N` writes
`raw/institutional/submissions/issue-N.json` (playlist id, institution, lecturer, faculty page,
syllabus and other material links, who submitted) and prints the steps: confirm the faculty page names
the lecturer, pull and merge the playlist as for any course (if it is on the lecturer's own channel, add
the channel to `pipeline/publishers.json` with the faculty page as evidence), label, set the submission's
`status` to `listed`, rebuild. The course page then carries the materials as links and a "submitted by
the lecturer" line. Nothing is uploaded or hosted; PsychTube links to the lectures where they are.

### Add a standalone institutional talk

Append `{"id": "<youtube id>", "inst": "<institution>", "kind": "talk" | "lecture", "ch": "<channel>"}` to
`raw/institutional/loose.json`, put the video's metadata in a `raw/youtube/meta_*.json` file, run
`python3 pipeline/make_inst_batches.py` (standalone talks are labeled like lectures) and rebuild. Only
the institution's own channel counts; a conference talk re-uploaded by a viewer does not.

### Add a primary source, a demo or a therapy session

Append an item to the right shelf in `pipeline/shelves.json`: the video (`p: youtube` with its id, or
`p: archive` with the item identifier and the MP4 file name), who uploaded it and how legitimate that
copy is (`official`, `archive`), the paper (`cite` plus `doi` or `url`), the `status` id if the finding
has a replication story, and 1–2 topics. Check the DOI against Crossref before committing. If there is
no authorized copy online, set `"video": null` and let the item stand for the paper. Put the video's
metadata in a `raw/youtube/meta_*.json` file (the keyless fetcher in `pipeline/NOTES.md`) and rebuild.

### Add or update a replication status

Edit the finding in `pipeline/taxonomy.json` → `contested_findings`: `status` (one of the ids in
`status_labels`), a note that says what the later research found, and `sources` with verified DOIs.
Then `python3 pipeline/make_taxonomy_md.py`, so the labelers' `TAXONOMY.md` lists it. To tag more
videos with a finding, run `python3 pipeline/replication_candidates.py` after a build (it has a keyword
pattern per finding; add one for a new finding), judge the candidates it writes into a
`work/replication/tags_<date>.jsonl` (`vid`, `contested`, `role`, `confidence`), and rebuild; the build
merges every `tags*.jsonl` and ignores tags under 0.6 confidence.

### Find more courses (the sweep)

`raw/sweep/channels.json` is a registry of ~390 institutional YouTube channels with their playlists,
and `raw/sweep/topic.json` the results of ~180 playlist searches (general, clinical neuropsychology,
psychotherapy demonstrations, neuroscience). `python3 pipeline/assemble_candidates.py`
turns everything not yet in `courses.json` into `work/triage/batch_NN.jsonl`; have Claude judge each
card by `pipeline/classify/INSTRUCTIONS_triage.md` into `out_NN.jsonl`, pull the kept playlists, and
continue as above. Re-running the sweep later (new channels, new playlists on known channels) only
needs the registry refreshed; everything already in `courses.json` is skipped.

### Refresh YouTube metadata

Titles, lengths and view counts are a snapshot. With a free YouTube Data API v3 key
(`export YOUTUBE_API_KEY=...`), `python3 pipeline/fetch_youtube_meta.py` refreshes
`raw/youtube/meta_api.json` in ~30 requests; rebuild afterwards. The keyless browser-side fetcher
used for the first build is described in `pipeline/NOTES.md`.

## What's deliberately missing

No accounts, no server, no tracking. History, likes, watch-later and lecture progress live in
`localStorage` (`pt:*` keys; Settings → Export/Import moves them between browsers). No infinite
feed: rows end. Autoplay-next is off by default and only ever offers the next lecture of the same
course. Thumbnails default to a frame from the middle of the video rather than the uploader's
designed one.

## Credit

Hacker News mentions: HackerTube (ODC-By) / open-index/hacker-news. Reddit: Arctic Shift archive,
comments remain their authors'. Stack Exchange: CC BY-SA. Video metadata: YouTube; titles and
channels belong to their creators. Labels and notes: written by Claude for this project; expect a few
mistakes and send them back.
