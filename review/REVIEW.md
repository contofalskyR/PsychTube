# PsychTube review

Reviewed at commit `539c6b8` (2026-11-03) against the seven principles in the review brief. Every number below was
measured on the committed data and code; the scripts that produced them are in `review/tools/`, and the fixes that
are small enough to write are in `review/patches/` (tested, applied in order with `git apply`, see the end).

**What I could not do.** This sandbox's network policy blocks youtube.com, i.ytimg.com, archive.org, api.crossref.org
and github.io. So: no liveness check of any video, no DOI re-verification, no reading of Internet Archive item rights,
and the YouTube player was exercised through a stub of the IFrame API. Where a finding depends on those, it says so.

---

## The short version

The front end is careful, the escaping is right, and the shelves and replication notes are the best thing here.
The project's weak point is the **institutional tier**. That's 96% of the catalog, and it trusts the *playlist* as the
unit of provenance:

- **Other people's videos are "Published by" an institution.** 1,305 "lectures" sit on a channel other than the
  playlist owner's, and 58 playlists are mostly other channels' videos (watch lists, not publications). Veritasium, CGP
  Grey, TED, Andrew Huberman's podcast and a re-upload channel are all shown as "Published by" an institution.
- **That distorts the rankings.** The first group on the Courses hub is "Independent lecturer", ahead of Stanford,
  because one therapist's `Psy 100` playlist contains three heavily vouched YouTuber videos. Their community scores make
  it the #2 "most recommended course" in the catalog.
- **The headline numbers overclaim.** "944 complete courses" is 212 taught courses, 109 lecture series and 623
  seminar and conference collections. "Vouches" on 25 cards are citations nobody recommended. One card says "Debunk"
  about a finding that replicated. The home row called "The canon" isn't the canon.
- **Legitimacy-first ordering isn't applied where people browse.** Topic pages sort by raw score: the Sleep page opens
  with *Joe Rogan Experience #1109*. Podcasts inside an institution's playlist get the institution's tier.
- **On a mid-range phone:**
  - An area page freezes for 15 s (97,000 DOM nodes).
  - The catalog takes 9.9 s to appear on slow 4G, with nothing on screen saying it's loading.
  - Switching tabs destroys the YouTube player.
- **The build isn't reproducible as claimed.** Output depends on `PYTHONHASHSEED`, and 12,845 upload dates are
  computed from the build-machine clock. `merge_pulled.py` can't read the files `yt_pull_runner.js` writes.

None of this needs a backend, accounts or anything the brief rules out. Most of it is fixed by the eight patches.

---

## Must fix

Bugs first; disagreements with design decisions are in their own section further down.

### M1. Institutional credit is per playlist, so other people's videos become an institution's lectures — principles 1, 2, 7

**Evidence**

- **Cross-channel items:** 1,305 institutional items are on a channel other than their playlist owner's, from 513
  channels. About 1,030 share no name with the institution; 460 of those are long-form.
- **Watch lists:** 58 playlists have half or more of their videos from other channels.
  - `GCC PSY 101 Part 1`: 18 of 18 are uploads by Seeker, N24Guy, bradh121…, including *Hilarious Freudian Slip Ups!!*
    and *Sigmund Freud's Interpretation of Dreams Pt. 2-4.wmv UNBLOCKED*. It's labelled an intro course.
  - New York University's `Moral and Political Psychology`: 12 of 12 are other channels' uploads.
  - `CPSY 323`: includes a "Professional Supplement Center" video.
  - In the two `ADC50x` courses, 37 of 41 videos come from other channels (Dr. Todd Grande, Doc Snipes, FRONTLINE…).
  - The Stanford Psychiatry collection: 247 of 270 items are on other channels, including 10 Andrew Huberman episodes
    and 7 World Economic Forum clips.
- **What the watch page says:** "Published by Independent lecturer. Lecture 17 of 29 in Psy 100: Learning, taught by
  John; put online by Veritasium." And for Huberman: "Published by Stanford Department of Psychiatry and Behavioral
  Sciences … put online by Andrew Huberman. It's here on the institution's authority." Both sentences were checked in
  a browser.
- **Knock-on effects:**
  - Those items get tier 0 and the institutional +1.0 vouch, with the ×1.2 breadth bonus on top.
  - They inflate their playlist's `pop`. The top three "Independent lecturer" playlists get 100% of their popularity
    from other channels' videos, which puts "Independent lecturer" first on the Courses hub.
  - They inflate the canon: 15 of the canon's top 100 carry the institutional vouch. CGP Grey's video scores 22.84
    against 18.29 for its community vouches alone.

**Cause**

- Membership is recorded per playlist item without checking the item's channel (`pipeline/build_catalog.py:254-271`).
- The only guard is a blocklist of a dozen YouTuber names (`THIRD_PARTY`, `:199`). It lacks TED, TED-Ed, TEDx,
  Huberman and podcasts, and it applies only to *unvouched* items (`:333`). A vouched third-party clip keeps the badge.

**Fix (`06-per-video-provenance.patch`)**

- A playlist item counts as the institution's only if its channel owns one of that institution's kept playlists or
  standalone talks, or is listed under a new `affiliated_channels` key in `pipeline/triage_overrides.json`.
- A playlist that is mostly other people's videos is dropped as a watch list.
- Items that fail the check keep their community vouches, if any, as ordinary community videos.
- The build writes `work/inst/crosschannel.json` (institution, channel, items) so the allowlist can be filled from
  evidence.

**Measured effect:** 60 watch lists dropped, 217 further items no longer credited, 16,947 → 15,556 videos. The top
taught courses by popularity become Sapolsky's, Toronto's and Yale's.

**The cost, stated plainly:** about 330 of the removed items are probably legitimate affiliates. These include Stanford
Medicine, Stanford CME, Stanford Center for Health Education and Wu Tsai for the Stanford collection, GBHI for UCSF, and
the Dalai Lama's channel for Mind & Life. The two NPTEL courses whose lectures sit on per-course NPTEL channels drop
out entirely. Roughly ten `affiliated_channels` entries restore those; the review file lists them.

### M2. The counts and labels overclaim — principle 1, and honesty in general

| Where | Says | Is |
|---|---|---|
| Home masthead (`app.js:364`), Courses row (`:370`), Data page (`:730`, `:740`), About (`:756`) | "16,205 lectures from **944 complete courses** published by 237 universities and scientific institutions" | 212 taught courses, 109 lecture series, **623 seminar / grand-rounds / conference collections** (8,950 of the 16,205 items are talks). "237 institutions" includes nine "Independent lecturer" labels covering 56 people's own channels. Some collections are on Panopto, the Internet Archive or are pseudo-playlists, not "public YouTube playlists". |
| Every card (`app.js:146`) | "**10** vouches" | `n = v.nrec \|\| v.nmention`: when nobody recommended a video, its *mention* count is shown as vouches. 25 videos, all HN items whose only mentions are `reference`/`joke`/`critical` (e.g. `-KSryJXDpZo`, 10 citations, 0 recommenders). |
| Every card (`app.js:147`) | "Published by MIT · **lecture** 12 of 130" | Hard-coded "lecture", even for a seminar talk; the course / seminar distinction disappears on every card outside the Courses hub. |
| Thumbnail tag (`app.js:161`) | "**Debunk**" | Shown for any `critique` badge, including the CogSci talk `0NM-oLagC1c` about a moderator of the framing effect, a finding the taxonomy marks *replicated*. The watch page and care page already say "pushes back"; the tag should too. |
| Home row "The canon" (`app.js:341`) | "The most vouched-for videos across all communities" | `V.filter(visible).slice(0,12)` is the legitimacy-weighted **rank**, not score, and includes unvouched items: only 6 of its 12 are the canon page's top 12. The canon page itself sorts by `score`, which includes the institutional vouch (M1). |
| Masthead | "**No algorithm**, no accounts" | There is a ranking formula, a "For you" recommender and a daily picker. "No accounts, no analytics" is true. |
| About (`app.js:759`) | "No autoplay-next" | There is an opt-in autoplay-next ("Play it" setting). |
| Watch page (`app.js:695`) | "**Why people recommend it**", followed by the uploader's YouTube description | For non-HN videos `summary` is the start of the YouTube description (e.g. *"enjoy a full day of top quality BS (\*Behavioural Science that is)"*). |
| Data page | "2,525 **vouching** comments" | `mentions`, including citations, jokes and critical ones. |

**Fix:** `01` (vouch line, kind-aware unit, Pushback, canon row) and `02` (counts by kind, publisher vs. lecturer
counts, copy).

### M3. Legitimacy-first ordering leaks in both directions — principle 2

- **Topic pages ignore `rank`** (`app.js:434`: `… || y.score - x.score`). NOTES says topic pages follow `rank`; they
  are the main browsing surface.
  - Consciousness: today's top 12 has five long-form non-institutional items (a Lex Fridman episode, Curt Jaimungal,
    NOVA…). By `rank` it would have none.
  - Sleep & dreams opens with *Joe Rogan Experience #1109*, then a Huberman episode.
- **Podcasts inside institutional playlists get tier 0**, because `formTier` checks `v.inst` before the podcast test
  (`app.js:29-30`). 23 long-form podcast items rank as an institution's own lecture (Huberman, *Evergood Podcast*,
  *ADHD Awareness Podcast*, Stanford CME episodes).
- **The institutions' own lectures are penalised when they aren't in a pulled playlist.** 12 long-form videos on
  channels the sweep registry lists as institutional (Stanford, UCTV, the Royal Institution, Uppsala…) are tier 1
  (×0.5), including *Stanford's Sapolsky On Depression in U.S.* (score 23.5).
- **Podcast detection is a channel-name regex plus HackerTube's `type`.** The community screening schema has no `type`
  field, so 259 of 609 community videos (43%) have none. I found only three likely misses among long-form community
  videos (e.g. *ActInf Livestream #013.1*), so the regex is adequate *for the community tier*. The real leak is the
  institutional one above.

**Fix:**

- `01` puts the podcast test first and sorts topic pages by `rank`.
- `06` removes most re-listed podcasts at the source.
- For the 12 penalised videos, export the set of institutional channel ids and treat `chid ∈ set` as tier 0. Not
  patched.

### M4. Long lists freeze a phone, and the first load has no loading state

Measured with Playwright on a Moto G4 profile with 4× CPU throttling (Lighthouse's mobile preset); the scripts are in
`review/tools/`.

| Route | Main-thread render | DOM nodes | Cards |
|---|---|---|---|
| `#a-brain` (area page) | **15.1 s** | 96,829 | 6,952 |
| `#longs` | **8.2 s** | 63,039 | 4,511 |
| `#t-how-the-brain-works` | **7.6 s** | 41,366 | 2,962 |
| `#courses?shelf=all` | 0.85 s | 13,868 | 946 |
| `#home` | 0.03 s | 3,035 | 226 |
| search keystroke (after the 220 ms debounce) | 0.26–0.35 s | | 200 |

`data.js` is 9.46 MB, 1.68 MB as transferred with gzip. Time until the catalog is visible: **2.7 s on fast 4G, 9.9 s
on slow 4G, 20 s on 3G.** Before that the page shows the header and rail over an empty `<main>`. The JS heap holds
27 MB after load, and app start-up is a single 521 ms long task.

**Fix:**

- `03` renders 60 cards with an explicit "Show 60 more · N left" button, never infinite scroll, so rows still end.
  Area page: 15.1 s → 0.09 s, 883 nodes.
- `02` builds the search index on the first search instead of at start-up. Start-up long task 521 → 397 ms, heap at
  load 27 → 17 MB. The first search pays 0.65 s once; later keystrokes take 0.13–0.19 s.
- `01` puts "Loading the catalog…" in `<main>`.

Splitting `data.js` is under "Consider".

### M5. Switching tabs or locking the phone destroys the YouTube player

`visibilitychange` → `player.stop()` → `yt.destroy()` (`app.js:632`, `:636`). The `<video>` player is paused, and the
Panopto progress ticker stops and isn't restarted.

Reproduced with a stub IFrame API: after one hide/show cycle the iframe is gone and the box holds an empty
`<div id="player">`. Long lectures are exactly what people leave playing in another tab.

**Fix (`01`):** each player gets a `save()`, and hiding the page saves and flushes without stopping anything. Verified:
the player survives, and progress is still written.

### M6. Three pages or links are broken outright

- **Clips page.** Each thumbnail link is empty and the whole row (title, channel, every timestamp button) is clipped
  out of sight. The cause is `thumb(v).replace('<div class="thumb">', "")` (`app.js:519`): it no longer matches because
  `thumb()` emits `class="thumb "` with a trailing space. The trailing `</div>` is still removed, so the unclosed div,
  which has `overflow: hidden`, swallows the row. Fix in `01` with a shared `thumbInner()`.
- **Shelf status chips.** They link to `#care?status=failed#care-<id>`. The router reads the status as
  `failed#care-<id>`, so the page shows **no findings** (`app.js:567`). Fix in `01`: `?status=…&f=<id>`, scrolled into
  view.
- **"Skip to content".** It links to `#main`, which the router maps to the home page (`app.js:804`). From a watch page,
  the skip link takes a keyboard user away from the page. Fix in `01`: a click handler that focuses `<main>`.

All three were verified broken before and fixed after in a browser.

### M7. Publisher legitimacy is decided once, at low confidence, and never re-checked — principle 1b

`INSTRUCTIONS_triage.md:55` tells the model to keep an ambiguous publisher at confidence ≤ 0.6 because "the next stage
sees the actual lectures and can still drop it". The next stage, `INSTRUCTIONS_courses.md:29`, only asks whether the
subject is psychology. Nobody re-checks the publisher.

**Result:**

- 299 collections (4,601 lectures) were kept at triage confidence ≤ 0.6.
- 30 have a triage note that literally says "instructor unverified", "affiliation unverified", "institution not
  evident" or "ambiguous". Examples:
  - `Psy 100: Learning` on "Dr John LMFT" ("clinician-instructor status unverified")
  - `UCD Psych 1000` on "by Christina Collins"
  - `Basics of Neurobiology` on "Arveen Kaur" ("speaker and host unverified")
  - `Memory` on a channel called "IIT Roorkee July 2018" ("ambiguous", 0.4)
- They all render as "Published by …" at tier 0, the same authority as MIT OpenCourseWare.

Related: "University of Consciousness, Qualia (UCQ)" is credited as an institution (137 lectures) on the strength of
its channel name. The lectures look like a real researcher's course, but the credit should name the person and their
university, not the channel.

**Fix:** a second, narrow pass over `confidence ≤ 0.6` and "Independent lecturer" collections that answers only "whose
channel is this, and who teaches?", writing `inst`/`lecturer` corrections into `triage_overrides.json`. Until then,
show unaffiliated personal channels as "a lecturer's own channel (affiliation not verified)" and rank them tier 1.
Not patched; it's a labeling round.

### M8. Non-English and exam-prep content got in — principle 7

The playlist triage checks English. Per-lecture labels and the community screening don't. `INSTRUCTIONS_community.md`
has no language rule and `INSTRUCTIONS_institutional.md` has none either. Found:

- `BD 101: Childhood and Growing Up` (Raja Mahendra Pratap Singh University). Seven **B.Ed. exam-revision sessions**
  (MCQs and classes), several with Hindi titles. The course card itself describes them as "MCQ review sessions", and
  they're filed as an *intro course*. Exam prep is explicitly excluded by triage.
- Five Chinese-language versions of webinars inside the Alan Hu Foundation series.
- Spanish-language modules in UC Davis MIND's *Autism Talks and Lectures*.
- Three French-language McGill Cares webcasts.
- An Urdu explainer from a third-party channel inside `PSY-496`.
- A COVID talk from BBRFI with a Hindi title, probably in Hindi.
- A Russian film in *FENS History of Neuroscience*.
- A Russian pop-psychology talk (Kurpatov) on the community side.

**Fix:** add `english` to the per-lecture and community label schemas, and as a cheap guard, drop items whose title is
mostly in a non-Latin script unless they are on a shelf. `review/tools/audit_data.py` prints the current count.

### M9. The build is not reproducible as documented, and the pull → merge step is broken

**Rebuild output depends on the hash seed.** A fresh clone rebuilds in 0.24 s offline, but `site/data.js` differs by
`PYTHONHASHSEED`: seeds 0/1/2 give three different files, and none matches the committed one. The cause is `rel`
lists: co-citation groups are sets, and ties in `Counter.most_common` follow set iteration order
(`build_catalog.py:530`).

**Dates are computed from the build clock.**

- `approx_pub` resolves "15y ago" against `utcnow()` at build time (`:217-224`). A rebuild next year shifts the year of
  all 12,845 approximate dates. 1,112 of them already read "2026-11-01" (the build month) for videos that were months
  old at pull time.
- `generated` is today's date (`:632`).
- `utcnow` / `utcfromtimestamp` are deprecated since Python 3.12.

**`merge_pulled.py` can't read its input.** It iterates the pull file's top level (`:42`), but
`yt_pull_runner.js`'s `__pullChunks()` writes `{pulled, courses, errors}`. On the committed
`raw/institutional/pulled_2026-11-02.json` it sees three "playlists" and adds nothing.

**It also overwrites the record of when things were pulled.** It defaults an unknown `kind` to `"course"` (`:62`) and
stamps `courses.json` with today's date on every run (`:69`), losing the pull date.

**Fix (`05`):**

- Ties are broken by id.
- `SOURCE_DATE_EPOCH` pins `generated`.
- Relative ages resolve against the course's or file's `pulled` date (months resolved properly).
- `merge_pulled` unwraps the runner format, stamps each new course with its pull date, and defaults `kind` to
  `talks`, the weakest claim.

**Verified:** byte-identical output across seeds 0–3, no deprecation warnings with `-W error`. On the committed pull
file, `merge_pulled` now reproduces the NOTES numbers: 929 present, 73 duplicates, 9 too short, 7 dropped by
overrides.

---

## Should fix

### Data

- **S1. 568 catalog videos show a view count as their channel** ("673", "1.8K") and have no views or date. They are in
  83 lectures of NPTEL's *Neuroscience of Human Movement* and elsewhere, and the cause is in `yt_helpers.js:39`. In the
  `lockupViewModel` branch, `rows[0].metadataParts[0]` is assumed to be the byline. When YouTube omits the byline
  (every video is the owner's), row 0 is "views · age". Parser fix in `08`; `06` repairs existing items at build time.
- **S2. The score rewards one person's persistence** (`score_video`, `build_catalog.py:290-307`).
  - Repeat mentions add `0.15×w` each, without limit. One HN user linked *Bonhoeffer's Theory of Stupidity* 15 times.
  - Every distinct month with a mention adds 0.3, even when it's the same person each month. *George Lakoff: Moral
    Politics* has 10 mentions by one author across 12 months and scores 9.43 with 3 recommenders; 51 single-recommender
    videos score ≥ 2.5.
  - A downvoted Reddit comment still adds 0.3 (`:156`). An unknown Reddit score is treated as upvoted (`:155`).
  - Stack Exchange *questions* count as recommendations (weight 0.8 ≥ 0.7). *"After watching a fairly engaging TEDx
    talk… is this right?"* makes the talk "1 vouch", and so does a question disputing an AsapSCIENCE claim.
  - `07` (a design change, yours to take) caps repeats at two per person, counts months by each recommender's first
    recommendation, and zeroes downvoted comments. 54 scores change and 19 of the canon's top 20 stay. Not patched:
    weighting SE questions by whether they endorse or dispute the video, which needs a stance label like HN's.
- **S3. Replication coverage is narrower than the 66 findings suggest** (principle 4).
  - The labelers were told to use contested ids "from TAXONOMY.md", and `TAXONOMY.md` lists only **30 of the 66**.
    Bystander effect, choice overload, learned helplessness, McGurk, framing, anchoring, ape language and 29 others
    could only arrive through the keyword pass or the shelves, so lectures in 16,000 institutional rows were never
    checked against them.
  - The status label "Fraud or retraction" exists, but **no finding has it**. Seven Dan Ariely videos carry no badge,
    including two versions of *The Truth About Dishonesty*. They present the research programme that produced the
    honesty-pledge study retracted in 2021.
  - The DOPS talks on psi phenomena (University of Virginia) carry no badge although `precognition-bem` exists.
  - Regenerate `TAXONOMY.md` from `taxonomy.json`, add a `fraud` finding, and re-run the keyword pass.
- **S4. Inherited topics are where the label errors are.**
  - 1,623 institutional items were never individually screened: no `keep`, no language check, no promo check. Their
    topics are their course's.
  - In my sample, 2 of the 4 inherited labels were wrong ("Darwin and Evolution — Context" as `sex-gender`; motor units
    as `brain-disorders`) against 2 of 36 per-lecture labels.
  - Run per-lecture labels for courses with more than ~10 lectures even when the card says one topic.
- **S5. `type` is derived from the series kind, not judged.**
  - Every item in a `course`/`series` playlist is `lecture`, so *Healthy Minds*, a TV interview show, is a lecture.
  - Every `talks` item is `talk`.
  - 305 items under four minutes in course/series playlists are "lecture N of M", 24 of them under a minute (*Tune in
    Dec. 21!*, 23-second trailers). The promo filter only runs on talk collections (`:336`); extend it, or add a
    per-lecture `promo` flag.
- **S6. Standalone-talk intake trusts names.**
  - 80 of 108 `loose.json` items are on channels that own no kept playlist and aren't in the sweep registry. Their only
    check is that the channel *name* looks like the institution.
  - Two are credited to "TEDx", one of them a TED-channel talk.
  - `loose.json` bypasses `triage_overrides.json` (the overrides are only applied in `merge_pulled.py`).
  - `06` applies `drop_inst` to standalone talks and adds TEDx. Better still, store `chid` in `loose.json` and require
    it to belong to the institution.
- **S7. 24 catalog videos are unlisted** on YouTube (`unl: true`), among the 3,498 whose exact metadata exists. Eight
  are Anderson Todd's Toronto lectures; others include Stanford, Harvard, Oxford, Royal Institution and UCL uploads. For the 12,845
  `approx` items this is unknown. An uploader who unlisted a video didn't publish it publicly, so skip `unl` items
  unless a community vouched for them.
- **S8. Liveness is effectively unverified.**
  - For 3,488 of the 3,498 catalog videos with fetched metadata, `st` is `UNPLAYABLE` ("Video unavailable"), including
    Sapolsky's lecture 1 and Veritasium's *Is Most Published Research Wrong?*. The keyless player call was degraded, and
    the build sensibly ignores `st`.
  - But nothing else checks deadness: the 12,845 `approx` items were alive on pull day, and that is all we know.
  - A monthly Data API refresh (`fetch_youtube_meta.py` exists) as a GitHub Action would fix this.
- **S9. Institution names are split.**
  - Columbia ×6, Harvard ×6, Stanford ×6, UCLA ×5, MIT ×4, `University of California Television` and
    `… (UCTV)`, `IIT Roorkee` and `IIT Roorkee (NPTEL)`, and nine "Independent lecturer" labels.
  - This inflates the institution count and fragments the hub.
  - `INST_SHORT` covers 26 of 304 names. Most chips show full names like "Columbia University (Center for Science and
    Society)".
  - Use a canonical institution plus an optional unit ("Columbia University · Zuckerman Institute"), group by the
    canonical name, and derive `short` from a table.
- **S10. Shelf provenance overclaims in a few places** (principle 3).
  - Spot-check of 15 items against their uploaders: all 14 YouTube uploaders match the claimed channel; the Internet
    Archive item couldn't be checked from here (details in Appendix B).
  - But the Primary sources tagline promises "the original films… as they were recorded". *Patient H.M.* is a 2016
    PBS NewsHour report (its note says so honestly), and *Kanzi* is a 2007 TED talk. The card label still says
    "Primary source". Add a per-item `form` ("original recording" / "documentary of the time" / "later report") and
    show it.
  - Auto-added therapy items get `legit: official` because a playlist re-listed them (`build_catalog.py:457`). That's
    how five Dr. Todd Grande role-plays reached the therapy shelf via City Vision University.
  - DATA.md says auto-added therapy items have `tp-` ids, but the curated ones do too. Export the build's `auto: true`.
  - "Internet Archive" is not the same as "authorized". The Shostrom films are in the Archive's `educationalfilms`
    collection. I couldn't check from here who uploaded them or under what rights, and as far as I know the series is
    still sold by its distributor. Record each IA item's uploader and `licenseurl`/`rights` in
    `shelves.json`; if a film is still sold, principle 3 puts it with Gloria: paper and note, no player. I couldn't
    read the metadata from here.

### Front end

- **S11. Lecture progress is overwritten across tabs.**
  - NOTES says "only dirty state is written, so a stale in-memory copy never overwrites what another tab saved". But
    `flushProgress` writes the whole object (`app.js:106`), so tab A erases what tab B recorded since A loaded.
  - "Mark unwatched" deletes the record, so a merge can't tell new from old.
  - "Clear history" also wipes **every course's progress**, with no confirmation (`:723`). "Clear everything" has none
    either (`:780`).
  - Import ignores the settings it exports (`:778`), including the Teach-me background.
  - `01` merges on flush (newest `ts` wins), writes a dated "unwatched" record, asks before clearing, keeps progress on
    "Clear history", and imports settings. History, likes and watch-later are still written whole; NOTES says so after
    `08`.
- **S12. Router and keyboard.**
  - A malformed escape (`#q-%E0%A4%A`) throws `URIError` and leaves the previous page on screen (`:795`).
  - A "?" inside a search is cut off, because the hash is decoded before it is split.
  - `Esc` calls `history.back()` even on the first page, which leaves the site (`:838`).
  - Arrow keys are hijacked everywhere, including from a focused `<video>`, so native seeking breaks on archive.org
    lectures (`:845`).
  - `l`/`w`/`t` are single-character shortcuts with no way to turn them off (WCAG 2.1.4, level A).
  - `01` fixes all but the last; add a Settings toggle for that one.
- **S13. Search.**
  - Terms of 7+ characters lose two letters (`:258`), and matching is by substring, so "placebo" → "place". The top
    result for *placebo* was **Simon Sinek on Millennials in the Work*place***, the second a crow "dis*place*ment"
    experiment, and the placebo lecture third.
  - "ai" matches "br*ai*n" and "Adel*ai*de".
  - `02` matches whole words and word prefixes, strips punctuation and stopwords, and uses a small suffix stemmer
    (prosopagnosia → prosopagnosics, aphasia → aphasic). After the patch, *placebo* returns 9 results and the first
    three are all placebo lectures.
- **S14. Contrast (WCAG AA 4.5:1), computed from the CSS tokens.**
  - Dark: the replication tag is white on coral at **2.74:1**. It is the most important trust signal on a card.
    `.faint` on panels is 4.0–4.5.
  - Light: all `.faint` text is 4.18; the Reddit, HN and institution chips are 3.17 / 3.73 / 4.34; failed-status chips
    are 3.86; the "Handle with care" heading is 4.21.
  - The thumbnail tag is coral for every status, so "Mixed evidence" looks as alarming as "Did not replicate".
  - `04` fixes the tokens (every pair ≥ 4.6:1, verified) and grades the tags like the status chips.
- **S15. ARIA and focus.**
  - The filter links are `<a role="button" aria-pressed>`. Space doesn't activate them (it scrolls the page), and the
    groups have no names.
  - The rail's icon glyphs are read aloud.
  - The progress bar has no name.
  - After a route change, focus stays on a destroyed element, so screen-reader users get no announcement. Move focus to
    `<h1>` or `<main>` after `route()`; this one is not patched.
  - `04` makes the filters honest links with `aria-current` and group labels, hides the glyphs, names the bar, and
    honours reduced motion in the one `smooth` scroll.
- **S16. Theme.**
  - Light-OS visitors get dark by default (`app.js:54`).
  - Because the theme is applied by `app.js`, after the 1.7 MB `data.js`, every load paints in the OS theme and then
    flips, which takes seconds on a phone.
  - The theme button can never return to "system".
  - `01` applies the saved theme in `<head>` before first paint. Whether the default should be `system` is your call.
- **S17. Two latent crashes and some dead code.**
  - `seriesRow` (`app.js:345`) is computed on every home render, is never used, and throws if a series' first video is
    missing.
  - `tagFor` dereferences `PT.contested[id].name` without a guard.
  - `FIRESIDE_TYPES` (`:26`) is unused.
  - `forYou`'s shuffle is `sort(() => r() - 0.5)` (`:205`): biased, and engine-dependent, so Safari and Chrome pick a
    different "Start here" row on the same day.

### Docs

- **S18. Docs that disagree with the code (fixed in `08`).**
  - NOTES says "one mention with 3+ upvotes"; the code accepts 2+ (`build_catalog.py:356`).
  - NOTES's tracker claim: see S11.
  - DATA.md doesn't say that empty, zero and false fields are omitted. `nrec` is present on 584 of 16,947 videos, so an
    agent doing `v["nrec"]` crashes.
  - DATA.md says Stack Exchange content is CC BY-SA 4.0; older posts are 2.5 or 3.0.
  - The README's "add a course" step runs `make_inst_batches.py` without `--only-mixed`, which queues 1,654 old lectures
    for relabeling.
  - Not patched: DATA.md's `type` list misses `commentary`, `news` and `comedy`.

---

## Consider

- **C1. Split the payload.**
  - The institutional tier is 96% of the rows and most visitors start on home, Courses or a shelf. Ship
    `data-core.js` (vouched videos, shelves, series index, contested), about 1 MB, and load `data-inst.js` on demand or
    after first render. `data.js` grew from 3.0 to 9.5 MB over the last seven data commits.
  - Even without splitting, giving `data.js` a content hash would let it be cached long-term.
  - The claude.ai copy is 13.4 MB of its 16 MB budget and has been growing 0.2–0.6 MB per recent round; add a size
    guard to `build_artifact.py`. Only 677 of 16,947 videos (4%) have an embedded thumbnail there.
- **C2. A Content-Security-Policy.** Nothing is injectable today: every data string is escaped, all 21 `target=_blank`
  links carry `rel="noopener"`, hrefs come from `https?://` regexes or curated files, and eight injection attempts
  across the hash routes rendered nothing. But four inline `onerror`/`onload` handlers prevent a strict CSP. Move them
  to one delegated listener and add a `<meta>` CSP that allows only the YouTube, Panopto and archive.org hosts. Also
  `esc()` the `<option>` values (`app.js:423`) for consistency.
- **C3. Self-host Bricolage Grotesque** (OFL). Every page view currently contacts Google Fonts, alongside about 200
  `i.ytimg.com` thumbnails and the IFrame API. "No analytics" is true; "no tracking" would need this caveat.
- **C4. A refresh path for courses.** `merge_pulled` skips any playlist already present, so new lectures, deletions
  and retitlings never arrive. A playlist pulled again next term is ignored.
- **C5. Fragile regexes.** They have little effect in today's data (about five relevant playlists), but anchor them
  with `\b`:
  - `EXAM` excludes on "exam" in "Examples", "tutor" in "tutorials", "academy" and "NET" anywhere. *Counselling Role
    play Examples* and Gilad Feldman's *Open-science tutorials* never reached triage.
  - `YOUTUBER`'s bare `TED` matches "anima**ted**", "manifes**ted**" and any channel with "Associated" or
    "Integrated".
- **C6. Privacy.** Reddit usernames are shown next to quotes. In this data only one quote is a sensitive first-person
  disclosure (childhood abuse, r/neurophilosophy, shown on two videos), but the export keeps it permanently. Screen
  quotes for self-disclosure, and consider "a Redditor in r/…" instead of usernames.
- **C7.** The two *Human Behavioral Biology (2010)* collections are different recordings: only 4 of 25 lecture durations
  match. The Stanford School of Humanities and Sciences one probably isn't 2010. Two identical names on one page confuse.

---

## Disagreements with design decisions

These aren't bugs. Each says which principle I think it serves or strains.

- **D1. The headline describes 3.4% of the catalog.** *"The psychology videos that psychology people
  keep telling each other to watch — and the courses universities put online"* sits over 584 vouched videos and 16,205
  institutional items, 8,950 of them seminar and conference talks. Lead with what it is: a catalog of what
  institutions published, with the community's picks and the receipts. It serves principle 1 more honestly.
- **D2. "Teach me something I don't know" is the second section on the home page,** with twelve background chips
  above the Courses row and the canon. That's the most prominent slot after the masthead, and principle 5 says quiet.
  Make it one line ("Teach me something I don't know →") or move it below the shelves.
- **D3. Seminars, grand rounds and conference talks rank with taught courses (tier 0).** Principle 1 says they are "a
  speaker's own account, not peer-reviewed". Principle 2 says the institution's own lecture comes first. They pull
  against each other. 623 talk collections now share the top tier with 212 courses on every topic page. A tier of 0.75
  for `talks` would keep them above podcasts and below courses.
- **D4. Unaffiliated personal channels are in the institutional tier.** "Lecturers' own channels" was meant for Jordan
  Peterson's and Steve Joordens's courses. It now covers 56 channels and 1,448 lectures, many with no evident
  affiliation. Either verify the affiliation (M7) or give them their own label and tier 1. This is principle 1b.
- **D5. The community tier has no copy-legitimacy rule, while the shelves have a strict one** (principle 3). The
  canon's #2 is *The Century of the Self (Full Adam Curtis Documentary)* uploaded by "David Lessig", and the Barkley
  ADHD lectures come from "Adhd Videos". You can't fix what people linked, but you can say "uploaded by a third party"
  on documentaries and TV whose channel isn't the broadcaster's.
- **D6. One blended `score`.** It mixes the institutional vouch and the breadth bonus into the number the canon and
  `pop` use. `06` exports a community-only `cscore` for the canon; consider exporting both everywhere and documenting
  which list uses which.
- **D7. Keyless innertube pulls as the primary method.** It works, but it's against YouTube's terms on automated access
  (see Licensing), fragile (S1), and produced unusable playability data (S8). The Data API script exists; make it the
  path and keep innertube for discovery only.
- **D8. Autoplay on and dark theme by default.** Small, but both are choices made for the viewer that a resource,
  rather than a feed, would leave to the OS and the user.

---

## The seven review areas, briefly

**1. Philosophy vs implementation.**

| Principle | Where it leaks |
|---|---|
| 1. Stated reason | M1, M2, M7, S6 |
| 2. Legitimacy first | M3, D3 |
| 3. Primary sources, legitimate copies | S10, D5 |
| 4. Replication honesty | S3; the Debunk tag in M2 |
| 5. Quiet side features | D2 |
| 6. Static, reproducible | M9 |
| 7. Scope | M8, M1, S5 |

The pathways and the picker are well built and stay out of the way except for D2.

**2. Data integrity.** The label sample is in Appendix A.

- Topic labels: 3 clearly wrong of 40 institutional plus 1 minor. 0 clearly wrong of 20 community, with 3 borderline
  scope keeps (a Technology Connections LED video, a helicopter skill video, a 3-minute personal vlog).
- The `type` field is uninformative on both tiers (S5; 43% missing for community videos).
- One contested badge is missing (Ariely), and none is wrong.
- Duplicates: 981 videos sit in two or more raw playlists. "First course wins" leaves 303 collections with gaps; that
  number also counts other drops. A genuinely mirrored course (same lectures under another playlist) is already caught
  by `merge_pulled`'s 60% overlap rule. I found no mirrors by title overlap; the HBB pair are different recordings.

**3. Front end.** Performance in M4. The tracker logic is sound apart from M5 and S11. The YouTube, Panopto and
`<video>` paths all record positions, resume five seconds back and mark lectures done at 92% or 45 s from the end. The
Teach-me seed (day × 131 + shuffle × 7919) works, but it rolls over at UTC midnight while "Start here" uses local
midnight, and it labels therapy and case items "a primary source" (fixed in `02`). Accessibility and theme are covered
in S12–S16.

**4. Security.** No injection found.

- `esc()` covers every data string in HTML.
- Hash input is only ever compared or URL-encoded, and `setTitle`'s textarea decode is safe.
- `rel="noopener"` is on every `target=_blank`, and all URLs in the data are http(s).
- The YouTube IFrame API and Panopto's `embedapi.min.js` are third-party scripts with full page access, standard for
  embeds. Pin Panopto's with SRI if their CDN serves a stable file.
- Remaining work is defence in depth (C2).

**5. Pipeline.**

- `make_inst_batches --only-mixed`, `assemble_candidates` and (after `05`) `merge_pulled` are idempotent when re-run.
- A rerun with new data appends new playlists only (C4).
- Reproducibility is in M9. `build_single.py` and `build_artifact.py` reproduce the committed outputs exactly.
- Regexes are covered in M1 (`THIRD_PARTY`), S5 (the promo filter) and C5. `THERAPY_RX`/`THERAPY_NEG` work today but
  are a long hand-tuned list.
- Topic inheritance is in S4.

**6. Licensing and terms.**

- **HackerTube (ODC-By 1.0).** Attribution is present on the site and in DATA.md. Add a `license`/`attribution` object
  inside `psychtube.json`, because the export travels without DATA.md. The HN comment text in the quotes remains the
  commenters'; short attributed quotes with links are the right shape.
- **Stack Exchange (CC BY-SA).** Author and link are kept, which is what attribution needs. Excerpts are adaptations,
  so the SE-derived parts stay CC BY-SA; say so in the JSON and link the licence. Versions are 2.5, 3.0 or 4.0 by post
  date.
- **Reddit.** Reddit's terms license content to Reddit, not to third parties, and Arctic Shift is an outside archive.
  Short quotation with attribution and a link is the defensible use. The risks: deleted comments persist in a permanent
  export, and usernames are tied to quotes. To reduce them:
  - drop quotes whose source is gone on each refresh
  - publish a removal contact
  - consider omitting usernames (C6)
- **Internet Archive.** Rights are per item.
  - The Berkeley webcasts were, as I understand it, released under a non-commercial Creative Commons licence, and
    streaming from archive.org (not re-hosting) is the right way to use them.
  - The shelf items need their IA `uploader`/`licenseurl`/`rights` recorded (S10). A user upload of a film that is still
    sold is not a legitimate copy just because it's on the Archive.
- **YouTube.**
  - Embedding through youtube-nocookie and the IFrame API is the sanctioned path.
  - The keyless innertube pulls are automated access to the service, which YouTube's Terms of Service prohibit except
    as YouTube allows. It's low practical risk for a hobby project but published as the method.
  - The official Data API path is the clean one, though its developer policies require stored API data to be refreshed
    or deleted on a schedule (30 days for most fields when I last read them). A monthly refresh Action would satisfy
    that and fix S8.
  - The claude.ai copy re-hosts 677 thumbnails as data URIs. Those are copies of uploaders' images; placeholders are
    the cautious option.

**7. Information design.**

- **The home page carries too much.** It has 21 sections and about 230 cards, roughly 7,500 px on a laptop. Nine of the
  sections are area rows that duplicate the Topics page. My cut:
  - masthead
  - Continue watching / Your courses
  - Start here
  - one row each for Courses, the canon and the four shelves
  - Handle with care
  - a link to Topics
- **Names.**
  - "Try it yourself" is excellent.
  - "Primary sources" is right once the later reports are marked (S10).
  - "Handle with care" is right for the home row. The page also lists findings that held up, so title the page
    "Replication notes", the phrase the watch page already uses.
  - "Debunk" → "Pushback".
  - "Longs" is a pun on Shorts that most visitors won't get, and it's a duration filter dressed as a section (4,511 items,
    mostly lectures). Call it "Over an hour" or drop it from the rail.
  - "Clips" (20 items, broken) earns a rail slot less than the shelves do. On a phone the bottom bar shows six of 16
    destinations, and the four shelves aren't among them.
- **Course vs seminar vs standalone talk.** The distinction is clear on the Courses hub and the watch page, and nowhere
  else. Every card said "lecture N of M" (fixed in `01`: "talk N of M"), and the "not peer-reviewed" caveat never
  appears on a card. Add a word, e.g. "Published by MIT · *seminar* talk 12 of 130".
- **Where people get lost.**
  - A grad student can't filter a topic page by kind (course / seminar / vouched). The "Course lectures" filter
    includes seminars. They also can't filter by level or year.
  - Grand-rounds titles such as *9-24-2025 Psychiatry George Engel Research Rounds | Anna Bailey* say nothing, and there
    is no summary to help.
  - A layperson meets "vouches", "Longs", masthead statistics, a form asking for an academic background, and topic
    pages with thousands of items.

---

## The three changes I would make first

1. **Make institutional provenance per video.** Apply `06`, then fill `affiliated_channels` from
   `work/inst/crosschannel.json`. Run the narrow publisher re-check (M7) over the low-confidence and "Independent
   lecturer" collections. It's the change with the most consequence: it fixes the Courses hub order, the canon's
   inflation, podcasts at tier 0, and YouTubers labelled as lectures.
2. **Make every count and label say exactly what it is.** Apply `01` and `02`: courses, series and talks counted
   separately; a vouch is a recommender; Pushback; the canon row is the canon; topic pages follow `rank`; "talk N of M".
   This is the cheapest honesty win, and it's what a first-time visitor reads.
3. **Make it survive a phone.** Apply `01` and `03`: paged lists, a player that survives backgrounding, a loading
   state, the theme before first paint. Then split `data.js` (C1).

## The one thing I would not touch

**The shelves' rule that an experiment with no authorized copy is listed with its paper and no player, together with
the "whose copy" line on every item.** Milgram, Asch, Little Albert, Harlow, the Bobo doll, the visual cliff and the
Strange Situation stand there as papers and notes, not as bootlegs. It's the clearest statement of what this project
is, the thing no other video site does, and the rule most likely to erode one "just link the YouTube upload" request at
a time.

---

## Appendix A — label sample

Seeded random samples (`random.seed(42)` over institutional items, `random.seed(7)` over community items). Verdicts
are mine, against `pipeline/classify/TAXONOMY.md` and `taxonomy.json`.

**40 institutional items.** Topics: 34 right; 3 wrong (#1, #12, #35); 1 weak (#32); 2 defensible defaults on
uninformative titles (#11, #27). Type: 2 wrong (#14, #31), 2 generous (#4, #30). Contested badges: none, and none
missing. Provenance: 3 issues. Data: 2 numeric-channel items.

| # | Item | Verdict |
|---|---|---|
| 1 | Botwin, *Darwin and Evolution (Part 1) — Context* (Independent lecturer), `sex-gender` (inherited) | **wrong topic**: history-of-psychology / behavioral-genetics; course card inherited |
| 2 | IIT Kanpur, *Neuroimaging – 2*, `brain-tech, psych-research` | right |
| 3 | MIT 9.40, *Hopfield Networks*, `ai-and-mind, memory` | right |
| 4 | *Ch. 10: Consciousness — Saldivar — UTRGV* (6.5-min chapter overview), `consciousness` | right; "lecture" is generous; credited "Independent lecturer" though the title names UTRGV |
| 5 | UC Davis MIND, *Culturally Grounded Parent Training*, `parenting` | right |
| 6 | UCLA, *Morning Open Discussion*, neurotechnology symposium, `brain-tech…` (inherited) | right |
| 7 | *Mindscape: Laura Roberts…* (Menninger Clinic channel), credited Stanford Psychiatry | topics right; **wrong publisher** (M1) |
| 8 | IIT Bombay, *Obstacles in Attaining Wellbeing*, `happiness-meaning, mindfulness` | right |
| 9 | 2011 Heller Lecture, Isabel Gauthier, `perception, intelligence-expertise` | right |
| 10 | IIT Guwahati, *Erikson's Psychosocial Stages*, `child-development, adolescence-aging, personality` | right |
| 11 | Rochester, *George Engel Research Rounds, Anna Bailey*, `psychiatry-medication` | uninformative title; default topic |
| 12 | Bermúdez, *Ownership and the space of the body*, `consciousness, ai-and-mind` | **`ai-and-mind` wrong**; perception |
| 13 | *IPN Retreat 2022 pt.5* (McGill IPN channel), credited "Ruthazer Lab" | topic ok; publisher is the IPN, not the lab |
| 14 | BBRF *Healthy Minds — 413 — Memory*, type `lecture` | **type wrong**: a TV interview show |
| 15 | Gresham, Goriely, *Folds in your brain* | right |
| 16 | Neuromatch, homeostatic plasticity and neurodevelopmental disorders | right |
| 17 | IIT Madras, *#59 Cerebellum*, channel shown as **"673"** | topic right; **channel field is a view count** (S1) |
| 18 | MIT 14.13, *Mid-Term Review* | right (housekeeping with teaching) |
| 19 | MIT 9.35, *Auditory Scene Analysis* | right |
| 20 | UCL, *Mind of a London cabbie* | right |
| 21 | Stanford Parenting Center, teens and COVID | right |
| 22 | Columbia Grand Rounds, gender affirmation | right |
| 23 | BNA, maternal sensitivity circuits | right |
| 24 | SPSP 2014, *Life in Business School* | right (career session) |
| 25 | MIT BMM summer course, Barbu | right |
| 26 | Dana Foundation, *The Anxious Brain* | right |
| 27 | Berkeley *Philosophy 3 — 2014-09-03* | course-level topics on an uninformative title; fine |
| 28 | UW, program co-design with Native American communities | right |
| 29 | UNM, law and mental health | right |
| 30 | *Dr. Bev Knox Course Introduction — Learn Psychology While You Sleep* (179 s) | a promo, not a lecture; the "learn while you sleep" framing deserves a look at the channel |
| 31 | BBRF *Healthy Minds — 406* | **type wrong** (TV show) |
| 32 | IIT Madras, *#20 Motor Units*, channel "1.8K", `brain-disorders` (inherited) | **weak topic**; channel field bug |
| 33 | Stanford, computational neuropsychiatry | right |
| 34 | APA, Minority Mental Health Summit | right |
| 35 | Neuromatch, *W initialization in SF learning*, `ai-and-mind, learning-studying` | **`learning-studying` wrong** (it means human study skills) |
| 36 | UC Davis MIND, comorbidity genetics | right |
| 37 | C-STAR, rTMS for aphasia | right |
| 38 | McGovern, Spring Symposium | right |
| 39 | Yale PSYC 110, *Why Are People Different?* | right |
| 40 | SMU, *Memory* (instructor's channel) | right |

**20 community items.** Topics: right on all 20. Scope: 3 borderline keeps (#1, #11, #18). Type: 9 empty. Vouch
semantics: 4 issues (#3, #9, #16, #20). Badges: 1 missing (#15). Provenance: 2 issues (#13, #17).

| # | Item | Verdict |
|---|---|---|
| 1 | Technology Connections, *The Weird World in RGB* | borderline scope (light technology) |
| 2 | Dennett at the RI | right |
| 3 | *Nudgestock 2021 — Full Live Stream* (11.9 h) | topics right; the one Reddit vouch doesn't recommend it; the description is shown as "why people recommend it" |
| 4 | ContraPoints, *Incels* (+ content note) | right |
| 5 | Hoffman, TED | right |
| 6 | *Eye Movements on EEG* | right |
| 7 | CGP Grey, teleportation | right |
| 8 | SciShow, face turning red | right |
| 9 | Vsauce, *Juvenoia* | right; **0 recommenders, card said "3 vouches"** |
| 10 | How to ADHD, *Wall of Awful* | right |
| 11 | *Validation* (208 s personal vlog) | instructions say drop personal vlogs |
| 12 | HBR, small talk | right |
| 13 | Hofstadter, Stanford channel | right; **tier 1 although it is Stanford's own lecture** (M3) |
| 14 | Barkley, *Neuroanatomy of ADHD* ("Adhd Videos" re-upload) | right; third-party copy (D5) |
| 15 | Ariely, RSA, *The Truth About Dishonesty* | right; **missing a fraud/retraction flag** (S3) |
| 16 | TEDx, *Your Friendly Successful Psychopath* | right; **the "vouch" is an SE question doubting it** |
| 17 | Peterson, *Biblical Series I* | credited **University of Toronto**; the Biblical Series were public lectures, not a U of T course |
| 18 | SmarterEveryDay, helicopter hovering | borderline scope |
| 19 | Sapolsky, *23. Language*, badge `ape-language`/promotes | right |
| 20 | AsapSCIENCE, orgasms (+ content note) | right; the "vouch" is an SE question disputing a claim |

## Appendix B — shelf spot-check (15 random items, seed 20261103)

All 14 YouTube items' claimed uploaders match the actual channel in `raw/youtube/meta_*.json`. In order: FRONTLINE PBS,
Real Stories (Little Dot, a licensed distributor), Daniel Simons, FRONTIER FTD, BBC, Tourette Association, PBS
NewsHour, Cummings Center, Western University, Maryland Science Center, Parkinson Society BC, 60 Minutes, National
Geographic and Chris Chambers. The Internet Archive item (the 1950s VA aphasia film) could not be checked from here.

Notes:

- *Patient H.M.* is a 2016 news report, not research footage. The item text says so; the shelf tagline and card label
  don't.
- *Robbers Cave* is the archive's 5-minute history lesson with original footage, which is fine and honestly described.
- *Change blindness* is a demo uploaded by a researcher who is not the paradigm's author. "The researcher's channel"
  reads as if it were.
- No item used an unofficial re-upload.

## Appendix C — patches

`review/patches/`, made against `539c6b8`, applied in order with `git apply review/patches/0*.patch`. Patches 01,
03, 05, 07 and 08 also apply on their own; 02, 04 and 06 need the ones before them. Checked on a
fresh clone: all eight apply cleanly, and the result is identical to the tree I tested. They touch code and docs
only, not data. After applying 05–07, rebuild with `python3 pipeline/build_catalog.py`, then `build_artifact.py` and
`build_single.py`.

| Patch | Kind | What it changes | Verified |
|---|---|---|---|
| `01-frontend-bug-fixes` | bugs | podcast tier before institution; progress merge; vouch line and kind-aware unit; Pushback; Clips markup; canon row; topic `rank`; shelf status link; player `save()` on hide; clear-history confirm; settings import; router decoding; Esc depth; arrow keys; skip link; theme before paint; loading state | in browser, before and after |
| `02-honest-counts-copy-and-search` | copy + bug | counts by kind and publisher; Data, About, masthead copy; uploader descriptions labelled; Teach-me labels; word-aware search; lazy index | in browser |
| `03-paged-long-lists` | perf | 60 cards plus "Show more" on list pages and search | area page 15.1 s → 0.09 s |
| `04-contrast-aria-reduced-motion` | a11y | AA tokens in both themes; graded tags; filter links with `aria-current` and labels; hidden glyphs; progress name; reduced motion | computed styles |
| `05-reproducible-build` | bugs | rel tie-break; `SOURCE_DATE_EPOCH`; dates from pull day; deprecations; `merge_pulled` reads the runner format, stamps `pulled`, defaults `kind` to `talks` | byte-identical over 4 seeds |
| `06-per-video-provenance` | data policy | per-video credit; watch lists dropped; parse-slip repair; `cscore`; overrides applied to standalone talks; TEDx dropped; review file | counts above |
| `07-scoring-caps-design-change` | design | repeat cap, first-recommendation months, downvoted = 0 | 54 scores move |
| `08-parser-fix-and-docs` | bug + docs | `yt_helpers.js` byline parse; README, NOTES, DATA.md corrections | parser unit check |

## Appendix D — reproducing the measurements

See `review/tools/README.md`. In short: `python3 review/tools/audit_data.py` re-prints the data numbers;
`python3 -m http.server 8765 --directory site` plus the Playwright scripts re-run the browser checks. Playwright and
Chromium are assumed installed.
