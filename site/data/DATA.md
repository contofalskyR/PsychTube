# PsychTube data

The data behind PsychTube: the psychology videos that psychology people keep telling each other to
watch. Use it to build your own UI, recommender, syllabus, newsletter or analysis.

One file, `psychtube.json`, with this shape:

```json
{
  "generated": "YYYY-MM-DD",
  "stats": {"videos": 0, "vouched": 0, "mentions": 0, "sources": {"hn": 0, "reddit": 0, "se": 0}, "communities": 0, "series": 0,
            "inst": {"courses": 0, "lectures": 0, "loose": 0, "institutions": 0, "also_vouched": 0}},
  "areas": [{"id": "brain", "name": "Brain & Neuroscience", "topics": [{"id": "memory", "name": "Memory", "desc": "...", "n": 12}]}],
  "contested": {"power-posing": {"name": "...", "note": "...", "source": "...", "status": "failed",
                                 "sources": [{"cite": "Ranehill et al. (2015)...", "doi": "10.1177/0956797614553946"}]}},
  "status_labels": {"replicated": "Replicated", "smaller": "Smaller than claimed", "mixed": "Mixed evidence", "failed": "Did not replicate",
                    "overstated": "Overstated", "misreported": "Misreported", "myth": "Myth", "fraud": "Fraud or retraction", "reversed": "Reversed"},
  "shelves": [{"id": "originals", "name": "Primary sources", "short": "Originals", "tagline": "...",
               "items": [{"sid": "pavlov-1948-film", "vid": "<video id or null>", "title": "...", "year": 1948, "people": "...", "what": "...",
                          "paper": {"cite": "...", "doi": "..."}, "paper2": null, "alt": [{"label": "...", "url": "..."}], "status": "pavlov-bell",
                          "topics": ["learning-studying"], "legit": "archive", "uploader": "...", "p": "archive", "len": 1200}]}],
  "pathways": [{"id": "brain", "name": "From zero to the brain", "for": "...", "steps": [{"label": "...", "why": "...", "series": "c-yale-psyc-110-introduction-to-psychology"},
                                                                                     {"label": "...", "why": "...", "all": ["c-cns1-...", "c-cns3-..."]}, {"label": "...", "why": "...", "shelf": "cases"}, {"label": "...", "why": "...", "page": "care", "page_label": "Handle with care"}]}],
  "cw": ["suicide-self-harm", "eating-disorders", "sexual-content", "abuse-violence", "substance-use"],
  "institutions": [{"name": "MIT", "short": "MIT", "courses": 0, "lectures": 0, "pop": 0}],
  "series": [{"id": "c-mit-9-13-the-human-brain", "name": "MIT 9.13 The Human Brain", "inst": "MIT", "short": "MIT", "lecturer": "Nancy Kanwisher", "year": 2019,
              "kind": "course", "level": "intro", "note": "...", "n": 17, "total": 17, "vids": ["..."], "topics": ["..."],
              "vouched": 2, "pop": 3.1, "score": 20.1, "url": "https://www.youtube.com/playlist?list=...", "ch": "MIT OpenCourseWare", "chid": "...", "hours": 19.5,
              "readings": "https://ocw.mit.edu/courses/9-13-the-human-brain-spring-2019/"},
             {"id": "crashcourse", "name": "CrashCourse", "n": 5, "vids": ["..."], "topics": ["..."], "vouched": 5, "pop": 0, "score": 0, "hours": 1}],
  "videos": [ ...see below... ]
}
```

## For AI agents: start here

You were probably handed this file and asked to build something with it. Everything you need is in
`psychtube.json`; no network access or API key is required. Thumbnails need no API:
`https://i.ytimg.com/vi/<id>/hq2.jpg` is an automatic frame from the middle of the video (what
PsychTube shows) and `.../hqdefault.jpg` is the uploader's thumbnail. Embed a player with
`https://www.youtube-nocookie.com/embed/<id>` (add `?start=<seconds>` for clips).

## `videos[]`: one object per video, best-scored first

| field | meaning |
|---|---|
| `id` | 11-character YouTube id |
| `title`, `ch`, `chid` | title, channel name and channel id as shown on YouTube |
| `len`, `views`, `pub` | duration in seconds, view count and upload date (YYYY-MM-DD) at build time |
| `topics` | 1–3 topic ids from `areas[].topics[]`, best fit first; `area` is the area of the first one |
| `type` | talk, lecture, course, documentary, explainer, interview, podcast, tutorial, demo, other (when known); shelf videos not otherwise in the catalog are `documentary` (primary sources) or `demo` (demonstrations and therapy sessions) |
| `course`, `series` | whether it is one lecture of a series, and the `series[].id` it belongs to |
| `p`, `host`, `f` | present when the video is not on YouTube. `p: "panopto"` with the Panopto `host` (e.g. `harvard.hosted.panopto.com`): `id` is the Panopto session id, the watch page is `https://<host>/Panopto/Pages/Viewer.aspx?id=<id>`, the embed is `https://<host>/Panopto/Pages/Embed.aspx?id=<id>` and a thumbnail is `https://<host>/Panopto/Services/FrameGrabber.svc/FrameRedirect?objectId=<id>&mode=Delivery`. `p: "archive"` (`host: "archive.org"`): `id` is the Internet Archive item identifier of this lecture (UC Berkeley webcasts: `ucberkeley_webcast_<original YouTube id>`), `f` the MP4 file name inside it; play `https://archive.org/download/<id>/<f>` in a `<video>` element (or embed `https://archive.org/embed/<id>`; items without `f` are stream-only and must use the embed), the item page is `https://archive.org/details/<id>` and a thumbnail is `https://archive.org/services/img/<id>`. |
| `inst` | present on lectures from the institutional tier: `{"n": institution, "i": position in the playlist, "of": playlist length}` (the series id is in `series`). `approx: true` marks lectures whose `views`/`pub` were estimated from the playlist page rather than fetched exactly. `{"n": institution, "loose": true}` marks a **standalone talk**: a single lecture or talk an institution published outside any playlist (a university's named lecture, a hospital's grand rounds recording, a society's prize lecture); same institutional vouch, no series |
| `score` | PsychTube's ranking signal: distinct recommenders weighted by strength of recommendation, with a bonus when several communities agree and for the number of distinct months it was recommended |
| `nrec` | distinct people whose mention counted as a recommendation |
| `nmention` | all mentions found, including neutral citations and critical ones |
| `src` | mentions per source: `hn` (Hacker News), `reddit`, `se` (Psychology & Neuroscience Stack Exchange) |
| `communities` | where it was mentioned, most often first: "Hacker News", "r/askpsychology", "Psychology & Neuroscience SE", … |
| `why`, `summary`, `quote` | one line on why people recommend it, a 2–3 sentence summary and a pull quote (for Hacker News videos these come from HackerTube's Claude-written cards; otherwise `summary` is the start of the YouTube description) |
| `vouches` | up to 12 of the mentions: `s` (source), `c` (community), `a` (author), `d` (YYYY-MM), `k` (kind: strong_rec, rec, reference, critical, joke, comment, post, question, answer), `q` (a short quote), `u` (link to the original), `up` (upvotes where known), `t` (timestamp in seconds when the link pointed at a moment), `thread` (the discussion it appeared in) |
| `badge` | `{"id", "role"}` when the video presents (`role: "promotes"`) or critiques (`role: "critique"`) a contested finding, or is the original footage of it (`role: "source"`); look the id up in `contested`, whose `status` says what became of the finding and whose `sources[]` are the replication or review papers (DOIs verified) |
| `shelf`, `orig` | present on the curated shelves (`shelves[]`): `shelf` lists the shelf ids the video sits on and `orig` is its card — `{sid, shelf, people, year, what, paper, paper2, alt, uploader, legit}` — the people behind it, the paper it belongs to (`paper.doi` or `paper.url`), alternative copies and how legitimate the copy is (`legit`: `official` = the rights holder's, institution's or researcher's own upload; `archive` = a library or archive collection) |
| `cw` | content notes that apply (ids from `cw`) |
| `first`, `last`, `months` | first and last year it was mentioned, and how many distinct months it was recommended |
| `clips` | timestamps (seconds) people linked to directly |
| `rel` | ids of videos recommended by the same people (co-recommendation), strongest first |
| `kw` | a few of the uploader's YouTube keywords |

## Two tiers: vouched videos and university courses

Videos come in on two different authorities. **Community-vouched** videos (`nrec ≥ 1`) are there
because people in psychology forums recommended them. **Institutional** lectures (`inst` present) are
there because a university, one of its lecturers, or a scientific institution published the whole
course as a public playlist; every lecture of a kept course is included in order, and `nrec` is 0
unless a community also vouched for that lecture. Each institutional `series[]` entry carries the
institution (`inst`, `short`), `lecturer`, `year`, `kind` (`course` = a taught course in lecture
order, `series` = a themed lecture series, `talks` = a collection of separate talks: a research seminar
series, a hospital's grand rounds, the sessions of a conference — institutional, but not a course and
not peer-reviewed, so weigh a `talks` item as a speaker's own account of their work), `level`
(`intro`, `advanced`, `public`), a one-line `note`, the playlist `url`, `vouched` (how many of its
lectures the communities vouched for) and `pop` (their summed community score; sort courses by it for
"most recommended course"). `institutions[]` summarizes per institution.

## Shelves: primary sources, demonstrations, therapy in practice

`shelves[]` are four hand-curated lists (`pipeline/shelves.json` in the repository): **originals**, the
original films of classic experiments and case studies (Pavlov's laboratory, the Gesell infant films,
Skinner's pigeons, the 1964 split-brain film, the Stanford prison experiment footage, Robbers Cave, the
Gloria films, H.M. and Clive Wearing, …); **demos**, experiments that work on the viewer (the gorilla,
the McGurk effect, the rubber hand, the hollow mask, Stroop, binocular rivalry, …); and **therapy**,
psychotherapy as it is done — full sessions, role-plays, simulated psychiatric interviews and case
formulations from training institutes and university programs, including the three Shostrom "Three
Approaches to Psychotherapy" series (1965, 1977, 1986) from the Internet Archive; and **cases**,
clinical neuropsychology's textbook patients on film (the aphasias, hemispatial neglect,
prosopagnosia, blindsight, visual agnosia, alien hand, phantom limbs, deep brain stimulation,
locked-in syndrome, hemispherectomy, Phineas Gage…). Every item carries
the paper it belongs to (`paper.doi`, verified against Crossref) and, where there is one, the
replication `status`. Items whose `vid` is `null` have no authorized copy online (Little Albert, Harlow,
Asch, Milgram, Bobo doll, the visual cliff, the Strange Situation); they are listed for the paper and
the note, so a UI should show them without a player. Each item's `legit` says whose copy it is;
unofficial re-uploads were not used. The therapy shelf also picks up demonstration videos that a
labeled course brought in (role-plays, intake and case-formulation videos; `sid` prefixed `tp-`).
Shelf videos not otherwise in the catalog have `type` `documentary` (originals, cases) or `demo`
(demos, therapy).

## Pathways

`pathways[]` are nine suggested prerequisite orders through the courses (from zero to the brain,
clinical psychology, clinical neuropsychology, cognitive science, computational neuroscience, methods,
social and personality, consciousness, development). Each step points at one `series[].id`, at
several that belong together (`all`, in order), at a shelf id or at a page; they were written by hand
and resolved against the catalog at build time.

## Replication status

`contested` has 66 findings, each with a one-paragraph `note`, a `status` (`replicated`, `smaller`,
`mixed`, `failed`, `overstated`, `misreported`, `myth`, `fraud`, `reversed`; display text in
`status_labels`) and `sources[]` — the replication, meta-analysis or review papers the status rests on,
with verified DOIs. Videos reach a finding through `badge`: `promotes` (presents it as established),
`critique` (pushes back on it) or `source` (the original footage). Findings with status `replicated` are
reassuring, not cautionary: a UI should not flag those videos the way it flags `failed` ones.

## Ordering: institutional legitimacy first for long-form

The site orders long-form content (over 25 minutes) by legitimacy before popularity: an institution's own
lecture or a curated shelf copy ranks above a fireside chat, interview or independent talk, which ranks
above a podcast episode. In the site this is `rank = max(score, 1) × {1, 0.5, 0.25}` by tier, applied to
every list except the canon, which stays by community score. Short pieces — a demonstration, a clip, a
TED talk — are not penalised. The export does not carry `rank`; compute it from `len`, `inst`/`orig`,
`type` and `ch` if you want the same order, or order by `score` for the pure community view.

## Things to know before you build

- `score` is the community score plus 1.0 per institutional vouch, so a plain course lecture scores
  about 1.0 and anything above ~1.5 was recommended by someone. Filter with `nrec` when you want
  only what people recommended, or with `inst` when you want complete courses.

- Only `nrec` counts recommendations. A video with `nrec: 1` was recommended by one person (and may
  have been cited by others); decide whether that is enough for your use. Videos from Reddit and
  Stack Exchange needed either two recommenders or one upvoted mention to be included.
- `score` is comparable across videos; sort by it for "best of", sample from it for variety.
- Topic labels, `why`/`summary` lines, badges and content notes were written by an LLM (Claude).
  They are good, not perfect: expect a few percent to be off.
- Some talks exist under several YouTube ids. Dedupe by normalized title if that matters to you.
- A `badge` is a reading note, not a verdict on the whole video; the `contested[].note` text explains
  what later research found and `source` names it.

## How it was made

1. **Vouches were mined** from three places: every Hacker News comment linking a YouTube video
   (via [HackerTube's export](https://hackertube.org/data), where each comment was already labeled by
   Claude with a stance), comments and posts in psychology subreddits (via the
   [Arctic Shift](https://arctic-shift.photon-reddit.com) archive), and posts on
   [Psychology & Neuroscience Stack Exchange](https://psychology.stackexchange.com) (via its public API).
2. **Candidates were screened** by Claude: title, channel, description and the comments that linked
   the video were read, and only videos whose primary subject is psychology, neuroscience, mental
   health or behavior were kept, each filed under 1–3 topics from a 50-topic taxonomy.
3. **Scores** count distinct people, weighted by how strongly they recommended (an enthusiastic HN
   recommendation 1.5, a plain recommendation 1, a citation 0.4; an upvoted Stack Exchange answer
   1.2+; a Reddit comment 1 plus a bonus for upvotes), with a bonus when several communities agree.
4. **Contested findings** were tagged where a video presents a finding that later shrank, failed to
   replicate or was overstated (power posing, the Stanford Prison Experiment, the marshmallow test,
   ego depletion, …) and where a video critiques one — first from the classification pass, then from a
   keyword search over every title and description that Claude judged video by video
   (`work/replication/`). Each finding's status and sources were checked against Crossref.
5. **YouTube metadata** (title, channel, length, views, upload date) was fetched at build time and
   dead or private videos were dropped.

## License and attribution

Hacker News-derived records follow HackerTube's ODC-By 1.0 (credit HackerTube and the
open-index/hacker-news dataset). Stack Exchange content is CC BY-SA 4.0 (credit the authors via the
links). Reddit comments remain the work of their authors and are quoted briefly with links back.
Video titles and channel names belong to their creators. Labels, notes and summaries written for
PsychTube are released under ODC-By 1.0: use them for anything, just say where they came from.
Not affiliated with YouTube, Google, Reddit, Hacker News, Y Combinator or Stack Exchange.
