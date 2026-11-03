# PsychTube data

The data behind PsychTube: the psychology videos that psychology people keep telling each other to
watch. Use it to build your own UI, recommender, syllabus, newsletter or analysis.

One file, `psychtube.json`, with this shape:

```json
{
  "generated": "YYYY-MM-DD",
  "stats": {"videos": 0, "vouched": 0, "mentions": 0, "sources": {"hn": 0, "reddit": 0, "se": 0}, "communities": 0, "series": 0,
            "inst": {"courses": 0, "lectures": 0, "institutions": 0, "also_vouched": 0}},
  "areas": [{"id": "brain", "name": "Brain & Neuroscience", "topics": [{"id": "memory", "name": "Memory", "desc": "...", "n": 12}]}],
  "contested": {"power-posing": {"name": "...", "note": "...", "source": "..."}},
  "cw": ["suicide-self-harm", "eating-disorders", "sexual-content", "abuse-violence", "substance-use"],
  "institutions": [{"name": "MIT", "short": "MIT", "courses": 0, "lectures": 0, "pop": 0}],
  "series": [{"id": "c-mit-9-13-the-human-brain", "name": "MIT 9.13 The Human Brain", "inst": "MIT", "short": "MIT", "lecturer": "Nancy Kanwisher", "year": 2019,
              "kind": "course", "level": "intro", "note": "...", "n": 17, "total": 17, "vids": ["..."], "topics": ["..."],
              "vouched": 2, "pop": 3.1, "score": 20.1, "url": "https://www.youtube.com/playlist?list=...", "ch": "MIT OpenCourseWare", "chid": "...", "hours": 19.5},
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
| `type` | talk, lecture, course, documentary, explainer, interview, podcast, tutorial, demo, other (when known) |
| `course`, `series` | whether it is one lecture of a series, and the `series[].id` it belongs to |
| `p`, `host`, `f` | present when the video is not on YouTube. `p: "panopto"` with the Panopto `host` (e.g. `harvard.hosted.panopto.com`): `id` is the Panopto session id, the watch page is `https://<host>/Panopto/Pages/Viewer.aspx?id=<id>`, the embed is `https://<host>/Panopto/Pages/Embed.aspx?id=<id>` and a thumbnail is `https://<host>/Panopto/Services/FrameGrabber.svc/FrameRedirect?objectId=<id>&mode=Delivery`. `p: "archive"` (`host: "archive.org"`): `id` is the Internet Archive item identifier of this lecture (UC Berkeley webcasts: `ucberkeley_webcast_<original YouTube id>`), `f` the MP4 file name inside it; play `https://archive.org/download/<id>/<f>` in a `<video>` element (or embed `https://archive.org/embed/<id>`), the item page is `https://archive.org/details/<id>` and a thumbnail is `https://archive.org/services/img/<id>`. |
| `inst` | present on lectures from the institutional tier: `{"n": institution, "s": series id, "i": position in the playlist, "of": playlist length}`. `approx: true` marks lectures whose `views`/`pub` were estimated from the playlist page rather than fetched exactly |
| `score` | PsychTube's ranking signal: distinct recommenders weighted by strength of recommendation, with a bonus when several communities agree and for the number of distinct months it was recommended |
| `nrec` | distinct people whose mention counted as a recommendation |
| `nmention` | all mentions found, including neutral citations and critical ones |
| `src` | mentions per source: `hn` (Hacker News), `reddit`, `se` (Psychology & Neuroscience Stack Exchange) |
| `communities` | where it was mentioned, most often first: "Hacker News", "r/askpsychology", "Psychology & Neuroscience SE", … |
| `why`, `summary`, `quote` | one line on why people recommend it, a 2–3 sentence summary and a pull quote (for Hacker News videos these come from HackerTube's Claude-written cards; otherwise `summary` is the start of the YouTube description) |
| `vouches` | up to 12 of the mentions: `s` (source), `c` (community), `a` (author), `d` (YYYY-MM), `k` (kind: strong_rec, rec, reference, critical, joke, comment, post, question, answer), `q` (a short quote), `u` (link to the original), `up` (upvotes where known), `t` (timestamp in seconds when the link pointed at a moment), `thread` (the discussion it appeared in) |
| `badge` | `{"id", "role"}` when the video presents (`role: "promotes"`) or critiques (`role: "critique"`) a contested finding; look the id up in `contested` |
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
   ego depletion, …) and where a video critiques one.
5. **YouTube metadata** (title, channel, length, views, upload date) was fetched at build time and
   dead or private videos were dropped.

## License and attribution

Hacker News-derived records follow HackerTube's ODC-By 1.0 (credit HackerTube and the
open-index/hacker-news dataset). Stack Exchange content is CC BY-SA 4.0 (credit the authors via the
links). Reddit comments remain the work of their authors and are quoted briefly with links back.
Video titles and channel names belong to their creators. Labels, notes and summaries written for
PsychTube are released under ODC-By 1.0: use them for anything, just say where they came from.
Not affiliated with YouTube, Google, Reddit, Hacker News, Y Combinator or Stack Exchange.
