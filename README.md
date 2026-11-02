# PsychTube

The psychology videos that psychology people keep telling each other to watch — a static,
account-free video site built from community vouches (Hacker News via HackerTube's export,
psychology subreddits via the Arctic Shift archive, and Psychology & Neuroscience Stack Exchange),
with the receipts on every card and "handle with care" notes on findings that didn't hold up —
plus an **institutional tier**: complete psychology courses that universities, their lecturers and
scientific institutions published on YouTube (MIT OpenCourseWare, Yale Courses, Stanford, the IITs
via NPTEL, Gresham College, the Royal Institution, professors' own channels…), every lecture in
order, marked "published by" instead of a vouch count.

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
  taxonomy.json        50 topics in 9 areas + contested-findings notes + content-note ids
  build_catalog.py     merges every source, scores, groups series, writes site/data.js
  make_inst_batches.py writes the labeling inputs for university playlists (course cards + per-lecture topics)
  build_artifact.py    writes site/hosted/ from site/ + raw/youtube/thumbs_*.json
  overrides.json       manual label corrections applied on top of the LLM labels
  NOTES.md             how each source was pulled, scoring details, how to redo it
  classify/            the instructions Claude followed to screen videos and assign topics
  fetch_youtube_meta.py  (optional) refresh YouTube metadata with a Data API key
  reddit_crawler.py    (optional) pull more Reddit vouches from Arctic Shift on an open network
raw/                   compact source data: HackerTube rows for kept videos, Stack Exchange posts,
                       Reddit records, YouTube metadata snapshots, university playlists (raw/institutional/)
work/                  intermediate files (classification batches and outputs; work/inst/ for the courses)
```

## Rebuild the catalog

```
python3 pipeline/build_catalog.py
```

reads everything under `raw/` and `work/` and rewrites `site/data.js` and `site/data/psychtube.json`.
It is deterministic given the inputs, so re-running it after adding raw data is safe.

### Add more Reddit vouches

`pipeline/reddit_crawler.py` pages through the Arctic Shift API for a list of subreddits and writes
`raw/reddit/reddit_<timestamp>.json`. The archive rate-limits aggressively (expect "Timeout. Maybe
slow down a bit" responses; the script backs off and resumes). New videos then need labels: create
batches with `pipeline/make_batches.py` and have Claude (or any model) fill them in following
`work/classify_new/INSTRUCTIONS.md`, then rebuild.

### Add a university course

Append the playlist to `raw/institutional/courses.json` (`pid`, `inst`, `kind`, and the items as the
other entries have them; `pipeline/NOTES.md` shows the innertube calls that list a playlist, or use
the Data API's `playlistItems`), then `python3 pipeline/make_inst_batches.py`, label the new rows
with `pipeline/classify/INSTRUCTIONS_courses.md` and `INSTRUCTIONS_institutional.md`, and rebuild.
Keep to official channels and lecturers' own channels; mirrors get taken down.

### Refresh YouTube metadata

Titles, lengths and view counts are a snapshot. With a free YouTube Data API v3 key
(`export YOUTUBE_API_KEY=...`), `python3 pipeline/fetch_youtube_meta.py` refreshes
`raw/youtube/meta_api.json` in ~30 requests; rebuild afterwards. The keyless browser-side fetcher
used for the first build is described in `pipeline/NOTES.md`.

## What's deliberately missing

No accounts, no server, no tracking. History, likes and watch-later live in `localStorage`.
No autoplay-next and no infinite feed: rows end. Thumbnails default to a frame from the middle of
the video rather than the uploader's designed one.

## Credit

Hacker News mentions: HackerTube (ODC-By) / open-index/hacker-news. Reddit: Arctic Shift archive,
comments remain their authors'. Stack Exchange: CC BY-SA. Video metadata: YouTube; titles and
channels belong to their creators. Labels and notes: written by Claude for this project; expect a few
mistakes and send them back.
