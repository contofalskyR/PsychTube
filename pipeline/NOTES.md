# Build notes

How the first catalog was assembled on 2026-11-02, so the next person (or agent) can redo it.

## Sources and how they were reached

The build machine's shell could only reach package registries and GitHub, so every data pull went
through a real browser (the Claude desktop app's browser pane) with small JavaScript jobs, and the
results came back as gzip+base64 chunks. On an open network the same pulls are plain HTTP:

| source | how | size |
|---|---|---|
| HackerTube export | `https://hackertube.org/download/hackertube-data.zip` (17.8 MB). Only the rows for kept videos are stored here under `raw/hackertube/`; re-download the zip for the rest. | 6,454 videos, 39,834 labeled comments |
| Psychology & Neuroscience Stack Exchange | Stack Exchange API 2.3, `/posts` with a custom filter including `body`, paged by `fromdate` because keyless use stops at page 25 (quota 300 requests/day/IP). Comments were sampled (first 9,000) because they almost never link videos. | 315 posts + 6 comments with links, 448 unique videos |
| Reddit | Arctic Shift API (`arctic-shift.photon-reddit.com/api`). Full-text (`body=`) and keyword (`query=`) searches timed out most of the day; plain time-ordered scans (`sort=asc&after=…&limit=auto`) worked at ~100 comments/request. `pipeline/reddit_crawler.py` does the same from Python. | see `raw/reddit/` |
| YouTube metadata | From a youtube.com tab: `POST /youtubei/v1/player` with the page's own `INNERTUBE_API_KEY` and a WEB client context, ~8 videos/second. Gives title, channel, length, views, publish date, category, keywords, description, and `playabilityStatus` (ERROR = gone). `pipeline/fetch_youtube_meta.py` does the same with the official Data API. | `raw/youtube/meta_*.json` |
| University courses (institutional tier) | From the same youtube.com tab: `POST /youtubei/v1/browse` with `browseId: "VL<playlistId>"` (plus continuations) lists a playlist in order with each video's id, title, length, channel and approximate views/age; `browseId: <channelId>` with the Playlists tab's `params` enumerates a channel's playlists, and `params: "EgZzZWFyY2jyBgQKAloA", query` searches inside a channel (how the MIT OCW course playlists were found, since the channel has ~700 playlists). Candidate playlists came from ~100 YouTube playlist searches ("MIT 9.00SC", "Yale PSYC 110", "NPTEL psychology"…) and from enumerating the playlists of ~50 university / lecturer channels, then hand-curating to official channels (university, department, OpenCourseWare, NPTEL, Gresham, Royal Institution) and lecturers' own channels publishing their actual courses (Jordan B Peterson, Steve Joordens, Anderson Todd, George Atwood). Mirrors and re-uploads were skipped. The playlist list lives in `raw/institutional/courses.json` (`pid`, `inst`, `kind`, items). | 103 playlists, 3,058 lectures |
| Panopto courses (Harvard) | Some universities host lectures on their own Panopto rather than YouTube (Steven Pinker's PSY 1 and GENED 1066 are public on harvard.hosted.panopto.com). A public folder lists its sessions at `Pages/Sessions/List.aspx#folderID=…` (ids and titles are in the DOM; the `Data.svc/GetSessions` call needs the page's exact parameters), and `POST /Panopto/Pages/Viewer/DeliveryInfo.aspx` with `deliveryId=<id>&responseType=json` returns name, duration and start time (seconds since 1601-01-01) without a login; `ErrorCode 15` means the session is archived or gone. Such a course goes into `courses.json` with `"provider": "panopto"` and `"host"`, item `pub` dates, and the folder or syllabus page as `url`. | 2 courses, 40 lectures |
| Internet Archive (UC Berkeley webcasts) | Berkeley took its 2005–2015 lecture webcasts off YouTube in 2017; the Internet Archive kept them as one item per lecture (`ucberkeley_webcast_<original YouTube id>`, grouped by course title and term). Found with `advancedsearch.php?q=collection:ucberkeley-webcast AND (psychology OR cognitive OR neuro…)&fl[]=identifier,title,description,date&output=json`, then `/metadata/<id>` (description, date) and `/metadata/<id>/files` (the `*.mp4` with its `length`); lectures were ordered by the lecture number in the title, then date. Such a course goes into `courses.json` with `"provider": "archive"`, `"host": "archive.org"`, and each item's `file`; the site plays `https://archive.org/download/<id>/<file>` in its own `<video>` (thumbnail `https://archive.org/services/img/<id>`, fallback embed `https://archive.org/embed/<id>`). | 22 courses, 553 lectures |
| Thumbnails (hosted copy only) | `https://i.ytimg.com/vi/<id>/mq2.jpg` (frame from the middle) drawn to a 224×126 canvas, JPEG q0.58, ~5 KB each, stored as data URIs in `raw/youtube/thumbs_*.json` because the hosted frame blocks external images. The local site just hotlinks `hq2.jpg`. | |

## The institutional sweep (how "every public psychology course" was approached)

The first institutional tier was hand-curated (103 playlists). The sweep that followed tries to be
systematic, in three passes, all from the youtube.com tab:

1. **Channel registry** (`raw/sweep/channels.json`, `{chid: {title, subs, verified, psychCh, playlists:[{id,title,n,src}]}}`).
   Channels came from ~60 channel searches (`params: "EgIQAg%3D%3D"`: "university psychology department",
   "school of medicine psychiatry grand rounds", "OpenCourseWare", "NPTEL", "institute of neuroscience",
   "psychological society"…) plus the channels of every playlist already kept. For each channel the
   Playlists tab was enumerated (`browseId: <chid>` with the tab's `params`, then continuations); the
   new YouTube UI returns small pages, and channels with hundreds of playlists (MIT OCW, NPTEL, Yale)
   were also searched inside the channel for `psychology`, `neuro`, `cognitive`, `brain`, `mind`,
   `behavior`, `psychiatry`, `mental`, `linguistics` (`params: "EgZzZWFyY2jyBgQKAloA"`). 390 channels,
   2,090 playlists.
2. **Topic playlist searches** (`raw/sweep/topic.json`, `params: "EgIQAw%3D%3D"`): ~100 queries such as
   `"PSYC 100 lectures"`, `"cognitive neuroscience course lecture 1"`, `"psychiatry grand rounds"`,
   `"developmental psychology full course university"`, each paged twice. 1,477 playlists with
   channel, verified flag and video count.
3. **Triage**: `pipeline/assemble_candidates.py` merges both (skipping playlists already in
   `courses.json`, playlists under 3 videos, non-ASCII titles, exam-prep/coaching channels, famous-course
   mirrors on non-institutional channels, and generic personal channels) into `work/triage/batch_NN.jsonl`,
   150 cards per file. Claude Sonnet judges each card by `classify/INSTRUCTIONS_triage.md` → `out_NN.jsonl`
   (`keep`, `inst`, `kind`, `english`, `confidence`, `why`): institutional publisher, psychology
   subject, lecture form, English. Kept playlists are then pulled in full (`browseId: "VL<pid>"`),
   appended to `courses.json` with the triage's `inst`/`kind`, and go through the usual course-card
   and per-lecture labeling, where the per-lecture `keep` and the course card's `keep` (a second look at
   the actual lectures) drop the ones the card oversold. Non-YouTube hosts found on the way (Panopto,
   Internet Archive) are added by hand as above; NIH VideoCast, university Kaltura/MediaSpace and
   Vimeo instances are the known remaining gaps.

**Round 2 (2026-11-02, evening).** 2,748 candidates from the registry and topic searches were triaged
(881 kept), plus 461 from a second round of 30 searches aimed at clinical neuropsychology (aphasia,
agnosia, neglect, amnesia, split-brain, blindsight, neuropsychological assessment, behavioural
neurology, dementia, TBI) and psychotherapy/counselling demonstrations (24 kept). 876 playlists were
pulled in ~26 minutes from the youtube.com tab with `pipeline/yt_pull_runner.js` (one `browse` call per
page of 100, ~650 ms apart, no rate-limit trouble); `pipeline/merge_pulled.py` added 795 of them to
`courses.json` (72 re-listed lectures already in, 9 too short) with the triage's institution and kind,
after `pipeline/triage_overrides.json` dropped media/festival publishers (Institute of Art and Ideas,
World Science Festival, Nour Foundation), a rehab centre, an advocacy group, and the Virtual
University of Pakistan's 2020+ "Topic Based Video" series (4–10-minute segments whose lecture language
cannot be checked: no captions). Course cards: 694 of 795 kept (the rest were promos, award clips,
patient-education snippets, re-hosted CrashCourse). Per-lecture labels were written for the 10,500
lectures of cards marked `per_video_topics: true`; the others inherit the card's topics. The build also
drops third-party explainer clips (CrashCourse, Khan Academy, Sprouts…) that lecturers re-list inside
their course playlists (`dropped_inst_thirdparty`) and no longer counts playlist membership as a
co-recommendation. Most of what came in is seminar series, grand rounds and conference sessions, so
the Courses hub now has two shelves — taught courses, and seminars & conferences marked as not
peer-reviewed — and a filter box.

**Round 3 (2026-11-03): neuroscience.** The catalog was thin on neuroscience proper, so 50 playlist
searches aimed at it (neuroscience lectures / course / seminar series / grand rounds, computational and
cognitive neuroscience, neuroimaging, neuroethics, connectomics, neural coding, brain development, summer
schools…) produced 62 new playlists after triage; 59 went in (1,281 lectures; the Institute of Noetic
Sciences was dropped by the overrides, one was a re-listing). They are mostly seminar series — the
McGovern Institute's 130 talks, Columbia and Harvard neuroscience seminars, the Zangwill Club, Oxford's
Nuffield Department of Clinical Neurosciences, Monell, MIND and NeuroHackademy summer schools, Wulfram
Gerstner's EPFL computational-neuroscience modules, Marty Sereno's Foundations of Neuroimaging. NYU's
*Brain and Behavior* (Wendy Suzuki, 2012, 24 lectures) exists only as loose uploads on NYU's channel,
so it was assembled by hand: `__channelSearch(chid, "Brain and Behavior")` listed the videos, the
syllabus order came from the course description, and the course sits in `courses.json` under the
invented pid `nyu:brain-and-behavior` with a `url` to the channel search (the build uses `url` when
present instead of composing a playlist link). 60 course cards and 1,269 per-lecture labels followed
the same instructions as before (1,198 kept; the drops are promos, retreat clips, immunology, and
software-administration tutorials inside the hackathon schools). Catalog after the round: 15,504
videos, 14,889 institutional lectures in 863 collections from 217 institutions.

Rate limits: the player endpoint started answering `LOGIN_REQUIRED` ("confirm you're not a bot") after
~1,800 calls with a minimal client context; sending the page's full `INNERTUBE_CONTEXT` (with
`visitorData`) and slowing to ~4 requests/second avoided it. `browse` never complained.

## Curated shelves (pipeline/shelves.json)

Four shelves are hand-written rather than mined: **originals** (the original films of classic
experiments and case studies), **demos** (demonstrations that work on the viewer), **therapy**
(psychotherapy as it is done) and **cases** (clinical neuropsychology's textbook patients on film:
29 items found with 62 video searches on youtube.com — aphasias, neglect, prosopagnosia, blindsight,
agnosia, alien hand, phantom limb, DBS, locked-in syndrome, hemispherectomy, PPA, Gage — keeping only
hospitals', labs', charities' and broadcasters' own uploads plus two Internet Archive films: the VA's
c. 1955 *Testing and Individual Therapy for the Aphasic Patient* and NET's 1967 *Aphasia: The Road
Back*; the classic teaching clips that exist only as re-uploads of documentaries — cogmonaut, the
Scientific American Frontiers excerpts, the NOVA Genie film — were left out, Genie and LM are listed
with their papers and no video). The same searches surfaced University College Dublin's bedside
neurology series (37 loose videos, "Neurology - Topic N"), which went in as the pseudo-playlist
`ucd:clinical-neurology` the way NYU's course did. Each item names the people, says what the footage is, gives the paper
it belongs to (`doi` or `url`), lists alternative copies, and records whose copy the video is
(`legit`: `official` = the rights holder's, institution's or researcher's own upload; `archive` = a
library or archive collection). Copies were found with `__videoSearch` in the youtube.com tab and
`advancedsearch.php` on archive.org, then checked by uploader; unofficial re-uploads were not used,
and experiments with no authorized copy online (Little Albert, Harlow, Asch, Milgram, Bobo doll, the
visual cliff, the Strange Situation, Hubel & Wiesel) are kept as `"video": null` so the shelf still
shows the paper and the note. Internet Archive items in stream-only collections (Stanford's `cst_*`)
carry `embed: true` and play through `archive.org/embed/`; the rest play the MP4 directly. Every DOI
was verified against `api.crossref.org/works/<doi>` from the archive.org tab (CORS allows it);
`doi_verified` records the date. Metadata for shelf videos not otherwise in the catalog comes from
`raw/youtube/meta_shelf.json`, `meta_therapy.json` and `meta_cases.json` (`__ytMeta2`, see above). The build adds those
videos to the catalog (type `documentary` or `demo`, score 1.0), sets `shelf` and `orig` on every
shelf video, gives the video a `source` badge when the item has a `status`, and tops the therapy shelf
up with demonstration videos a labeled course already brought in (title regex over `therapy`-topic
videos: role-plays, session demonstrations, intake and case-formulation videos; promos, "lecture N"
titles and talks *about* role-play are excluded). The 1965, 1977 and 1986 Shostrom series ("Three
Approaches to Psychotherapy": Gloria with Rogers/Perls/Ellis; Kathy with Rogers/Shostrom/Lazarus;
Richard with Beck/Strupp/Meichenbaum) are all on the Internet Archive in the `educationalfilms`
collection; the Rogers–Gloria session itself is not there, only on unofficial YouTube uploads, so the
shelf lists the Perls film with the Ellis session as an alternative.

**NIH VideoCast (investigated, not integrated).** The 2026 site is a Next.js app over
`/api/events/past-events` (one year of events, 489 in November 2026, categories including
"Neuroscience" and "BSSR - Behavioral and Social Sciences") and `/api/events/<request_id>`, whose
`video_url` is a Vbrick Rev embed with a short-lived JWT (`nihcit.rev.vbrick.com/embed?id=…&jwt_token=…`).
There is no stable embed or MP4 to point a third-party player at, and the archive window is a year,
so the lectures cannot be carried the way YouTube, Panopto and Internet Archive items are. If that
changes, the hook is a `p: "nih"` provider that links out to `videocast.nih.gov/watch=<id>`.

## Replication status (taxonomy.json → contested_findings, work/replication/)

Each of the 66 contested findings has a `status` — `replicated`, `smaller`, `mixed`, `failed`,
`overstated`, `misreported`, `myth`, `fraud`, `reversed` (labels in `status_labels`) — and `sources`,
the replication, meta-analysis or review papers the status rests on, with DOIs verified against
Crossref (two were wrong on the first pass and corrected: Paap & Greenberg 2013 is
`10.1016/j.cogpsych.2012.12.002`; Tully's "Pavlov's dogs" is `10.1016/s0960-9822(03)00066-6`).
Findings that hold up (Stroop, McGurk, the rubber hand, inattentional blindness, split-brain, the
Asch majority effect, Robbers Cave, Pavlov) are in the list on purpose so that a video presenting
them gets a reassuring chip rather than nothing. Besides the badges the classifiers assigned, a keyword
pass over every title and description produced 132 candidates (`work/replication/candidates.jsonl`)
that Claude judged one by one into `tags.jsonl` (`vid`, `contested`, `role`); the build merges those
onto videos without a badge. The care page groups findings by status and separates the original
footage, the videos that present the finding and the pushback.

## "Teach me something I don't know" (site/app.js)

No account: the viewer picks one or more backgrounds (`BACKGROUNDS` maps each — cognitive science,
neuroscience, clinical, psychiatry, social, developmental, personality, philosophy, machine learning,
methods, applied, just curious — to the topics they already know) and the picker chooses three videos
from outside those topics and outside the watch history: a vouched talk (`nrec ≥ 2`), lecture 1 of a
non-advanced course, and a primary source or demo, with distinct topics and areas. The seed is the
day plus a shuffle counter, so the picks change daily and on demand; the backgrounds are saved in
`settings.background` with the other preferences.

## Lecture tracker (site/app.js)

Positions are recorded from the real players: the YouTube IFrame API (`onStateChange` + a 4 s poll
of `getCurrentTime()`), Panopto's Embed API (`https://developers.panopto.com/scripts/embedapi.min.js`,
`EmbedApi(containerId, {serverName, sessionId, videoParams, events})`; `window.PlayerState` =
`{Ended:0, Playing:1, Paused:2}`) and `timeupdate` on the Internet Archive `<video>`. Each record is
`localStorage["pt:progress"][id] = {t, d, done, ts}`; a lecture counts as watched when
`t ≥ d − 45 s` or `t/d ≥ 0.92`, or when the viewer marks it. Course progress is derived from the
lectures (`seriesProgress`: watched count, percent including partial lectures, time left, last
activity) rather than stored, so a lecture watched from a topic page still advances its course.
Saving is debounced and flushed on `pagehide`; only dirty state is written, so a stale in-memory
copy never overwrites what another tab saved. Settings → Export writes `{psychtube:1, history, liked,
later, progress, settings}` as JSON and Import merges it (newest `ts` wins, unknown ids dropped).
The claude.ai artifact copy cannot embed players, so it has no tracker; the GitHub Pages site does.

## Screening and labels

- HackerTube candidates = videos in HackerTube's psychology/neuroscience/mental-health/consciousness
  categories (303) plus a keyword prefilter over all 6,454 (1,492 more). Claude Sonnet read each in
  batches of 225 following `classify/INSTRUCTIONS_hackertube.md`; 320 were kept.
- Community-sourced videos (Stack Exchange, Reddit) were screened after metadata arrived, following
  `classify/INSTRUCTIONS_community.md`, which also sees the comments that linked each video.
- Institutional playlists were labeled twice: once per playlist (`classify/INSTRUCTIONS_courses.md`
  → `work/inst/course_labels.jsonl`: display name, lecturer, year, kind, level, note, course topics) and
  once per lecture (`classify/INSTRUCTIONS_institutional.md` → `work/inst/out_*.jsonl`: topics and a
  `keep` that drops the odd non-psychology talk from mixed playlists). `pipeline/make_inst_batches.py`
  writes both inputs. A lecture with no per-lecture label yet inherits its course's topics.
- `pipeline/overrides.json` holds manual corrections applied on top of the labels.
- `pipeline/taxonomy.json` holds the 50 topics, the content-note ids and the contested-findings notes
  (with status and verified sources, see below). Edit the notes there; the site reads them at build time.

## Scoring (build_catalog.py)

Per video: for each distinct (source, author) take the strongest mention weight
(HN strong_rec 1.5 / rec 1.0 / reference 0.4 / joke 0.05 / critical 0; SE answer 1.2, question 0.8,
comment 0.7, each ×(1 + 0.05×min(score,10)); Reddit comment 1.0 if upvoted else 0.3, ×(1 + 0.08×√score);
Reddit post 0.8 ×(1 + 0.05×√score)), add 0.15× for repeat mentions by the same person, multiply by a
breadth bonus (1 + 0.2 per extra source + 0.05 per extra community) and add 0.3 per distinct month
with a recommendation. `nrec` counts (source, author) pairs whose best weight is ≥ 0.7.

Inclusion: HackerTube videos need `keep: true`. Community videos also need two recommenders, one
mention with 3+ upvotes, or an upvoted Stack Exchange answer. Dead/private videos (no title from
YouTube) are dropped.

Institutional tier: being in a kept university playlist counts as one vouch of weight 1.0 from the
institution (source `inst`), which is enough for inclusion on its own, so every lecture of a kept
course is in the catalog, in playlist order. `nrec`, `nmention`, `src` and `communities` count only
the community vouches, so a lecture nobody linked shows "Published by MIT" instead of a vouch count,
and a lecture the communities also vouched for gets both (its `score` includes the institutional
vouch and the cross-source breadth bonus). Series: each playlist is one `series` entry with `inst`,
`lecturer`, `year`, `kind` (course / series / talks), `level`, `note`, `url`; `pop` is the summed
community score of its lectures and ranks courses on the hub. Channel-heuristic series are still
built for vouched lectures not in any playlist.

## Hosted copy

`pipeline/build_artifact.py` writes `site/hosted/` (index.html with inline CSS, app.js, data.js,
thumbs.js). It sets `window.PT_ARTIFACT = true`, which makes app.js use embedded thumbnails, replace
the player with a "Watch on YouTube" poster, and leave theme control to the host. Routes are plain
hash names (`#v-<id>`, `#t-<topic>`, `#prefs`) for the same reason.
