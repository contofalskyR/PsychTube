#!/usr/bin/env python3
"""PsychTube catalog builder.

Merges every vouch source into one catalog:
  raw/hackertube/videos_candidates.jsonl + work/classify/out_*.jsonl   (HN, labeled)
  raw/hackertube/mentions_kept.jsonl, related_kept.jsonl                (HN provenance / co-recs)
  raw/stackexchange/psychology_se.json                                  (Psych & Neuro Stack Exchange)
  raw/reddit/reddit_*.json                                              (Arctic Shift crawl of psych subreddits)
  raw/youtube/meta_*.json                                               (YouTube metadata, keyless)
  work/classify_new/out_*.jsonl                                         (labels for non-HN videos)
  raw/institutional/courses.json + work/inst/course_labels.jsonl        (university courses: every lecture, in order)
  work/inst/out_*.jsonl                                                 (per-lecture topic labels)

Writes:
  site/data.js            window.PT = {...}   (what the site loads)
  site/data/psychtube.json                   (the export)
  work/catalog_stats.json
"""
import collections
import datetime as dt
import glob
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

TAX = json.load(open(P("pipeline", "taxonomy.json")))
TOPIC_IDS = {t["id"] for a in TAX["areas"] for t in a["topics"]}
TOPIC_AREA = {t["id"]: a["id"] for a in TAX["areas"] for t in a["topics"]}
CONTESTED = {c["id"]: c for c in TAX["contested_findings"]}

# ---------------------------------------------------------------- helpers

def jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def clean(s, n):
    s = (s or "").replace("\r", " ").replace("\n", " ").replace("[VIDEO]", "(this video)").replace("[LINK]", "(link)")
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > n:
        s = s[: n - 1].rsplit(" ", 1)[0] + "…"
    return s


def parse_ts(t):
    """'1h2m3s' | '95s' | '95' -> seconds"""
    if t is None:
        return None
    t = str(t)
    if t.isdigit():
        return int(t)
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s?)?", t)
    if not m:
        return None
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def month_of(epoch):
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).strftime("%Y-%m")   # utcfromtimestamp is deprecated since 3.12


# ---------------------------------------------------------------- load labels

def load_labels(pattern):
    labels = {}
    for f in sorted(glob.glob(pattern)):
        for o in jsonl(f):
            labels[o["vid"]] = o
    return labels


hn_labels = load_labels(P("work", "classify", "out_*.jsonl"))
new_labels = load_labels(P("work", "classify_new", "out_*.jsonl"))
inst_labels = load_labels(P("work", "inst", "out_*.jsonl"))

# manual curation on top of the LLM labels (pipeline/overrides.json: vid -> fields)
if os.path.exists(P("pipeline", "overrides.json")):
    for vid, fields in json.load(open(P("pipeline", "overrides.json"))).items():
        if vid.startswith("_"):
            continue
        for labs in (hn_labels, new_labels, inst_labels):
            if vid in labs:
                labs[vid].update(fields)

# ---------------------------------------------------------------- YouTube meta

meta = {}
for f in sorted(glob.glob(P("raw", "youtube", "meta_*.json"))):
    for vid, m in json.load(open(f)).items():
        meta[vid] = m

# ---------------------------------------------------------------- collect vouches

videos = collections.defaultdict(lambda: {"vouches": [], "hn": None})

STANCE_W = {"strong_rec": 1.5, "rec": 1.0, "reference": 0.4, "joke": 0.05, "critical": 0.0}

# HN
hn_cands = {r["vid"]: r for r in jsonl(P("raw", "hackertube", "videos_candidates.jsonl"))}
for vid, lab in hn_labels.items():
    if not lab.get("keep") or vid not in hn_cands:
        continue
    videos[vid]["hn"] = hn_cands[vid]
for m in jsonl(P("raw", "hackertube", "mentions_kept.jsonl")):
    vid = m["vid"]
    if vid not in videos or videos[vid]["hn"] is None:
        continue
    videos[vid]["vouches"].append({
        "s": "hn", "c": "Hacker News", "a": m.get("author"), "d": m.get("month"),
        "k": m.get("stance"), "w": STANCE_W.get(m.get("stance"), 0.5),
        "q": clean(m.get("quote") or m.get("why") or m.get("text"), 220),
        "why": clean(m.get("why"), 120), "u": m.get("hn_url"), "up": None,
        "thread": clean(m.get("story_title"), 100), "t": None,
    })

hn_related = {r["vid"]: r["related"] for r in jsonl(P("raw", "hackertube", "related_kept.jsonl"))}

# Stack Exchange
se = json.load(open(P("raw", "stackexchange", "psychology_se.json"))) if os.path.exists(P("raw", "stackexchange", "psychology_se.json")) else {"posts": [], "comments": []}
SE_W = {"answer": 1.2, "question": 0.8, "comment": 0.7}
for p in se.get("posts", []) + se.get("comments", []):
    for v in p["v"]:
        videos[v["id"]]["vouches"].append({
            "s": "se", "c": "Psychology & Neuroscience SE", "a": p.get("a"), "d": month_of(p["t"]),
            "k": p["k"], "w": SE_W.get(p["k"], 0.7) * (1.0 + min(p.get("sc") or 0, 10) * 0.05),
            "q": clean(p.get("b"), 220), "u": p.get("link"), "up": p.get("sc"),
            "thread": clean(p.get("title"), 100), "t": parse_ts(v.get("t")),
        })

# Reddit
reddit_recs, reddit_posts = [], []
for f in sorted(glob.glob(P("raw", "reddit", "reddit_*.json"))):
    d = json.load(open(f))
    reddit_recs += d.get("records", [])
    reddit_posts += d.get("posts", [])
seen_rc = set()
for r in reddit_recs:
    if r["c"] in seen_rc:
        continue
    seen_rc.add(r["c"])
    sc = r.get("sc") if r.get("sc") is not None else 1
    w = (1.0 if sc >= 1 else 0.0) * (1.0 + min(max(sc, 0), 50) ** 0.5 * 0.08)   # sc <= 0: the community disagreed
    link = (r.get("l") or "").replace("t3_", "")
    for v in r["v"]:
        videos[v["id"]]["vouches"].append({
            "s": "reddit", "c": "r/" + r["s"], "a": r.get("a"), "d": month_of(r["t"]),
            "k": "comment", "w": w, "q": clean(r.get("b"), 220),
            "u": f"https://www.reddit.com/r/{r['s']}/comments/{link}/_/{r['c']}/" if link else None,
            "up": sc, "thread": None, "t": parse_ts(v.get("t")),
        })
seen_rp = set()
for p in reddit_posts:
    if p["id"] in seen_rp:
        continue
    seen_rp.add(p["id"])
    sc = p.get("sc") or 0
    w = 0.8 * (1.0 + min(sc, 200) ** 0.5 * 0.05)
    for v in p["v"]:
        videos[v["id"]]["vouches"].append({
            "s": "reddit", "c": "r/" + p["s"], "a": p.get("a"), "d": month_of(p["t"]),
            "k": "post", "w": w, "q": clean((p.get("ti") or "") + (" — " + p["st"] if p.get("st") else ""), 220),
            "u": f"https://www.reddit.com/r/{p['s']}/comments/{p['id']}/", "up": sc,
            "thread": clean(p.get("ti"), 100), "t": parse_ts(v.get("t")),
        })

# ---------------------------------------------------------------- institutional tier
# Complete courses and lecture collections published by universities, their faculty or scientific
# institutions (raw/institutional/courses.json, pulled playlist by playlist). Publication by the
# institution counts as one vouch of weight 1.0 ("institutional backing"); every lecture of a kept
# course is included, in order, whether or not a community ever linked it.

INST_SHORT = {
    "Massachusetts Institute of Technology": "MIT", "University of California Television": "UCTV",
    "Virtual University of Pakistan": "VU Pakistan", "The Royal Institution": "Royal Institution",
    "Royal College of Psychiatrists": "RCPsych", "University of New Mexico": "UNM", "University of Toronto": "U of Toronto",
    "Simon Fraser University": "SFU", "University of Edinburgh": "Edinburgh", "University of Sheffield": "Sheffield",
    "University of Amsterdam": "Amsterdam", "University of Oxford": "Oxford", "Harvard University": "Harvard",
    "Yale University": "Yale", "Stanford University": "Stanford", "Rutgers University": "Rutgers",
    "Biola University": "Biola", "Vanderbilt University": "Vanderbilt", "The Open University": "Open University",
    "IIT Guwahati (NPTEL)": "IIT Guwahati", "IIT Kanpur (NPTEL)": "IIT Kanpur", "IIT Madras (NPTEL)": "IIT Madras",
    "IIT Bombay (NPTEL)": "IIT Bombay", "IIT Delhi (NPTEL)": "IIT Delhi", "IISc Bengaluru (NPTEL)": "IISc",
    "CEC-UGC (India)": "UGC-CEC",
}
INST_W = 1.0
THIRD_PARTY = re.compile(r"CrashCourse|Crash Course|Khan ?Academy|Kurzgesagt|SciShow|Veritasium|Vsauce|AsapSCIENCE|Psych2Go|Sprouts|Practical Psychology|2-Minute Neuroscience|Neuro Transmissions|Big Think|Professor Dave|Bozeman|Amoeba Sisters|Osmosis|Ninja Nerd|Simply Psychology|Mr\.? Sinn|Cognito|Medicosis|The School of Life|Wondrium|Great Courses|National Geographic|^Vox$|Freethink|BBC", re.I)
inst_file = P("raw", "institutional", "courses.json")
inst_json = json.load(open(inst_file)) if os.path.exists(inst_file) else {"courses": []}
inst_courses = inst_json["courses"]
INST_PULLED = inst_json.get("pulled") or dt.date.today().isoformat()   # when a course has no pull date of its own
course_labels = {o["pid"]: o for o in jsonl(P("work", "inst", "course_labels.jsonl"))}
TRIAGE_OV = json.load(open(P("pipeline", "triage_overrides.json"), encoding="utf-8")) if os.path.exists(P("pipeline", "triage_overrides.json")) else {}
# the overrides also apply at build time, so a playlist dropped or re-credited after it was merged needs no re-merge
_drop_pid, _drop_inst, _rename = set(TRIAGE_OV.get("drop_pid", [])), set(TRIAGE_OV.get("drop_inst", [])), TRIAGE_OV.get("rename_inst", {})
_pid_inst = {k: v for k, v in (TRIAGE_OV.get("pid_inst") or {}).items() if not k.startswith("_")}
inst_courses = [c for c in inst_courses if c["pid"] not in _drop_pid and _rename.get(c["inst"], c["inst"]) not in _drop_inst]
for c in inst_courses:
    c["inst"] = _pid_inst.get(c["pid"]) or _rename.get(c["inst"], c["inst"])
    if not c.get("ownerId") and not c.get("provider") and c.get("items"):
        # a co-owned or ownerless playlist: the dominant channel is the owner if it holds at least half the items, otherwise it is nobody's
        top = collections.Counter(it.get("chid") for it in c["items"] if it.get("chid")).most_common(1)
        if top and top[0][1] * 2 >= len(c["items"]):
            c["ownerId"] = top[0][0]
            c["owner"] = next(it.get("ch") for it in c["items"] if it.get("chid") == top[0][0])
        else:
            c["ownerId"] = "?"              # no own channel: every item is someone else's (the watch-list rule below drops it)

# One institution, many labels: "Columbia University (Zuckerman Institute)", "Columbia University Department of Psychiatry" and
# "Columbia University" are one publisher with three units. pipeline/institutions.json maps each raw label to a canonical name
# and a unit; the hub groups by the canonical name, the chip shows its short form, the unit stays on the card.
INSTITUTIONS = json.load(open(P("pipeline", "institutions.json"), encoding="utf-8")) if os.path.exists(P("pipeline", "institutions.json")) else {"canon": {}, "short": {}}
INST_SHORT.update(INSTITUTIONS.get("short") or {})
# Publishers whose channel is a person's own, or whose name was all the triage had, were checked against institutional pages
# (pipeline/publishers.json, INSTRUCTIONS_publishers.md). A personal channel is "Independent lecturer" whatever the triage said:
# the university did not publish it, the lecturer did. ok=false keeps the collection but at tier 1, labelled "affiliation not verified".
PUBLISHERS = (json.load(open(P("pipeline", "publishers.json"), encoding="utf-8")) if os.path.exists(P("pipeline", "publishers.json")) else {}).get("channels", {})


def canon_inst(raw, ownerId=None):
    """raw institution label -> (canonical name, unit)."""
    pub = PUBLISHERS.get(ownerId or "")
    if pub and pub.get("personal"):
        return "Independent lecturer", pub.get("lecturer") or pub.get("channel") or raw
    row = INSTITUTIONS["canon"].get(raw)
    if row:
        return row["name"], row.get("unit")
    m = re.match(r"^Independent lecturer(?: \((.*)\))?$", raw)
    if m:
        return "Independent lecturer", m.group(1)
    m = re.match(r"^(.*?)\s*\((.*)\)$", raw)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return raw, None


def pub_key(name, unit):
    """who 'owns' a channel for provenance: the institution, or one lecturer (never all lecturers together)."""
    return f"{name} · {unit}" if name == "Independent lecturer" else name


for c in inst_courses:
    c["_canon"], c["_unit"] = canon_inst(c["inst"], c.get("ownerId"))
    c["_pk"] = pub_key(c["_canon"], c["_unit"])


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def approx_views(info):
    m = re.match(r"\s*([\d.,]+)\s*([KMB]?)", info or "")
    if not m:
        return None
    n = float(m.group(1).replace(",", "")) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2)]
    return int(n)


def approx_pub(info, pulled):
    """'3y ago' -> a date, resolved against the day the playlist was pulled, not the day of the build
    (resolving against the build clock moved 12,845 upload dates by a year every year)."""
    m = re.search(r"(\d+)\s*(y|mo|w|d|h)\b", info or "")
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    ref = dt.date.fromisoformat(pulled)
    if unit == "y":
        return f"{ref.year - n:04d}-01-01"
    if unit == "mo":
        y, mo = divmod(ref.year * 12 + ref.month - 1 - n, 12)
        return f"{y:04d}-{mo + 1:02d}-01"
    return ref.strftime("%Y-%m-01")


# Provenance is per video, not per playlist. A lecturer's playlist that re-lists a TED talk, a Veritasium video or a podcast
# episode does not make the institution its publisher, so a playlist item is credited only when it sits on one of the
# institution's own channels: a channel that owns one of its kept playlists or standalone talks, or one listed for it under
# "affiliated_channels" in triage_overrides.json. Other items keep their community vouches (if any) and lose the badge, the
# course position and the tier-0 rank. A playlist that is mostly other channels' videos is a watch list, not a publication.
inst_channels = collections.defaultdict(set)   # publisher key -> its own channel ids (canonical, so every Stanford unit's channel counts for every Stanford playlist)
for c in inst_courses:
    if c.get("ownerId") and c["ownerId"] != "?":
        inst_channels[c["_pk"]].add(c["ownerId"])
_loose_path = P("raw", "institutional", "loose.json")
for lv in (json.load(open(_loose_path, encoding="utf-8"))["videos"] if os.path.exists(_loose_path) else []):
    if (meta.get(lv["id"]) or {}).get("chid"):
        inst_channels[pub_key(*canon_inst(lv["inst"], meta[lv["id"]]["chid"]))].add(meta[lv["id"]]["chid"])
for _inst, _chids in (TRIAGE_OV.get("affiliated_channels") or {}).items():
    if not _inst.startswith("_"):
        inst_channels[_inst] |= set(_chids)
INST_CHANNEL_IDS = sorted({ch for s in inst_channels.values() for ch in s if PUBLISHERS.get(ch, {}).get("ok", True)})   # exported: a long video on one of these channels ranks as institutional even outside a pulled playlist
COUNT_RX = re.compile(r"[\d.,]+\s*[KMB]?(\s*views?)?", re.I)
cross_review = collections.Counter()   # (institution, channel) -> items not credited; written to work/inst/crosschannel.json for review
cross_n = watchlists = partials = 0


def own_item(it, c):
    """Repair the playlist-parse slip (a view count in the channel field) and say whether the item is the institution's own."""
    if not it.get("chid") and COUNT_RX.fullmatch(it.get("ch") or ""):
        it["info"] = (it.get("ch") or "") + " · " + (it.get("info") or "")
        it["ch"], it["chid"] = c.get("owner"), c.get("ownerId")
    if c.get("ownerId") == "?":
        return False
    return bool(c.get("provider")) or not it.get("chid") or not c.get("ownerId") or it["chid"] in inst_channels[c["_pk"]]


# Courses lecturers and institutions submit themselves (.github/ISSUE_TEMPLATE/submit-course.yml -> pipeline/intake_submission.py ->
# raw/institutional/submissions/issue-<n>.json). The lectures still arrive through the normal pull/label path; the submission adds the
# syllabus and other materials (links only) and the "submitted by the lecturer" line, once its status is "listed".
SUBMISSIONS = {}
for _f in sorted(glob.glob(P("raw", "institutional", "submissions", "issue-*.json"))):
    _sub = json.load(open(_f, encoding="utf-8"))
    if _sub.get("pid") and _sub.get("status") == "listed":
        SUBMISSIONS[_sub["pid"]] = _sub

inst_course = {}       # sid -> course record (series entry under construction)
inst_member = {}       # vid -> (sid, idx)
inst_meta = {}         # vid -> fallback metadata built from the playlist row
used_sids = set()
name_counts = collections.Counter(clean((course_labels.get(c["pid"]) or {}).get("name") or c["title"], 120) for c in inst_courses)
for c in inst_courses:
    cl = course_labels.get(c["pid"]) or {}
    if cl and not cl.get("keep", True):
        continue
    name = clean(cl.get("name") or c["title"], 120)
    if name_counts[name] > 1 and cl.get("year"):
        name = f"{name} ({cl['year']})"      # e.g. the 2007 and 2011 runs of Minsky's Society of Mind
    sid = "c-" + slug(name)[:56]
    while sid in used_sids:
        sid += "-" + c["pid"][-3:].lower()
    used_sids.add(sid)
    items = [it for it in c["items"] if it.get("title") not in ("[Private video]", "[Deleted video]")]
    own = {k for k, it in enumerate(items) if own_item(it, c)}
    partial = bool(items) and len(own) / len(items) < 0.5
    if partial and len(own) < 4:
        watchlists += 1                     # mostly other people's videos and almost none of its own: a watch list, not a publication
        for k, it in enumerate(items):
            if k not in own:
                cross_review[(c["_canon"], it.get("ch") or "?")] += 1
        continue
    if partial:
        partials += 1                       # a watch list that also carries the institution's own recordings: those are listed, the rest is not
    readings = next((u.rstrip(".,") for u in re.findall(r"https?://[^\s)>\]]+", c.get("desc") or "")
                     if re.search(r"ocw\.mit\.edu|oyc\.yale\.edu|open\.yale|\.edu/|\.ac\.uk|nptel|swayam|syllabus|course", u, re.I)
                     and not re.search(r"youtube|youtu\.be|twitter|facebook|instagram|bit\.ly|tinyurl|linkedin|tiktok|forms\.gle|patreon", u, re.I)), None)
    pub = PUBLISHERS.get(c.get("ownerId") or "") or {}
    inst_course[sid] = {
        "id": sid, "name": name, "inst": c["_canon"], "unit": c["_unit"], "short": INST_SHORT.get(c["_canon"], c["_canon"]), "provider": c.get("provider") or "youtube", "readings": readings,
        "lecturer": (pub.get("lecturer") if pub.get("personal") else None) or cl.get("lecturer") or "", "year": cl.get("year"), "kind": cl.get("kind") or c["kind"],
        "level": cl.get("level") or "", "note": clean(cl.get("note"), 200), "ctopics": [t for t in cl.get("topics", []) if t in TOPIC_IDS],
        "pid": c["pid"], "url": c.get("url") or f"https://www.youtube.com/playlist?list={c['pid']}", "ch": c.get("owner"), "chid": c.get("ownerId") if c.get("ownerId") != "?" else None,
        "total": len(items), "items": items, "topic_map": cl.get("topic_map") or {},
        "cross": len(items) - len(own), "partial": partial,
        "materials": (SUBMISSIONS.get(c["pid"]) or {}).get("materials") or None,
        "submitted": ({"by": SUBMISSIONS[c["pid"]].get("submitted_by", "other"), "issue": SUBMISSIONS[c["pid"]].get("issue"), "control": bool(SUBMISSIONS[c["pid"]].get("control_verified"))} if c["pid"] in SUBMISSIONS else None),
        # publisher check: who is behind a personal or name-only channel, and whether an institutional page confirms it
        "affil": pub.get("affil") if pub.get("personal") else None, "verified": bool(pub.get("verified")) if pub else None,
        "ok": pub.get("ok", True) if pub else True, "pubwhy": pub.get("why") if pub and not pub.get("ok", True) else None,
    }
    for k, it in enumerate(items):
        vid = it["id"]
        if k not in own:
            cross_n += 1; cross_review[(c["_canon"], it.get("ch") or "?")] += 1
            continue                        # another channel's video re-listed in this playlist: not the institution's
        if vid in inst_member:
            continue  # first course wins when a video sits in two playlists
        inst_member[vid] = (sid, it["idx"])
        inst_meta[vid] = {"title": it["title"], "ch": it.get("ch") or c.get("owner"), "chid": it.get("chid") or c.get("ownerId"),
                          "len": it.get("len"), "views": approx_views(it.get("info")), "pub": it.get("pub") or approx_pub(it.get("info"), c.get("pulled") or INST_PULLED),
                          "approx": not c.get("provider")}
        if c.get("provider"):           # not YouTube (e.g. a university's Panopto): the site needs the host to embed and link
            inst_meta[vid]["p"] = c["provider"]
            inst_meta[vid]["host"] = c.get("host")
            if it.get("file"):
                inst_meta[vid]["f"] = it["file"]   # Internet Archive: the MP4 file name, so the site can use its own <video> player
        videos[vid]["vouches"].append({
            "s": "inst", "c": c["_canon"], "a": c.get("owner"), "d": None, "k": "course", "w": INST_W if inst_course[sid]["ok"] else 0.5,
            "q": f"Lecture {it['idx']} of {len(items)} in {name}", "u": c.get("url") or f"https://www.youtube.com/playlist?list={c['pid']}",
            "up": None, "thread": None, "t": None,
        })

# ---------------------------------------------------------------- loose institutional videos (raw/institutional/loose.json)
# standalone lectures and talks an institution published outside any playlist: same institutional vouch, no series
inst_loose = {}
LOOSE = json.load(open(P("raw", "institutional", "loose.json"), encoding="utf-8"))["videos"] if os.path.exists(P("raw", "institutional", "loose.json")) else []
for lv in LOOSE:
    vid = lv["id"]
    if vid in inst_member or vid in inst_loose or lv["inst"] in _drop_inst:
        continue
    _chid = (meta.get(vid) or {}).get("chid")
    _name, _unit = canon_inst(_rename.get(lv["inst"], lv["inst"]), _chid)
    _pub = PUBLISHERS.get(_chid or "") or {}
    inst_loose[vid] = {"inst": _name, "unit": _unit, "kind": lv.get("kind") or "talk", "why": lv.get("why", ""), "ok": _pub.get("ok", True) if _pub else True}
    videos[vid]["vouches"].append({
        "s": "inst", "c": _name, "a": lv.get("ch") or _name, "d": None, "k": "talk", "w": INST_W if inst_loose[vid]["ok"] else 0.5,
        "q": f"A standalone {lv.get('kind') or 'talk'} published by {_name}", "u": f"https://www.youtube.com/watch?v={vid}",
        "up": None, "thread": None, "t": None,
    })

# ---------------------------------------------------------------- quotes that are personal disclosures (privacy)
# A recommendation still counts, but a commenter's own history of abuse, illness or self-harm is not shown next to their username.
SENSITIVE_RX = re.compile(r"\b(as someone (who|in|with|recovering)|as a (survivor|victim)|i (was|am|have been|'ve been|got) (sexually |physically |emotionally )?(abused|molested|raped|assaulted)"
                          r"|i('m| am| was) (a |an )?(recovering|addict|suicidal|anorexic|bulimic|bipolar|schizophrenic|psychotic)"
                          r"|my (abuser|rapist|eating disorder|anorexia|bulimia|psychosis|schizophrenia|bipolar|ptsd|suicide attempt|self.?harm|addiction|relapse|overdose|trauma|diagnosis)\b"
                          r"|i (tried|attempted) (to kill myself|suicide)|i (self.?harm|cut myself|overdosed|relapsed)|in therapy (right now|for)|(childhood|child|sexual) abuse (i |that i |survivor))", re.I)
withheld = 0
for rec in videos.values():
    for vo in rec["vouches"]:
        if vo["s"] != "inst" and vo.get("q") and SENSITIVE_RX.search(vo["q"]):
            vo["q"] = "(quote withheld: the comment is a personal disclosure)"
            withheld += 1

# ---------------------------------------------------------------- score + select

def score_video(vouches):
    """distinct-voucher weighted sum, with a breadth bonus across communities."""
    best_by_author = {}
    extra = 0.0
    repeats = collections.Counter()
    first_month = {}                       # month of each recommender's first recommendation
    for v in vouches:
        key = (v["s"], (v.get("a") or "?").lower())
        if key in best_by_author:
            if repeats[key] < 2:           # at most two repeat mentions per person count (one user linked a video 15 times)
                extra += 0.15 * v["w"]
            repeats[key] += 1
            best_by_author[key] = max(best_by_author[key], v["w"])
        else:
            best_by_author[key] = v["w"]
        if v["w"] >= 0.7 and v.get("d") and v["s"] != "inst":
            first_month[key] = min(first_month.get(key, v["d"]), v["d"])
    base = sum(best_by_author.values()) + extra
    communities = {v["c"] for v in vouches if v["w"] >= 0.7}
    sources = {v["s"] for v in vouches if v["w"] >= 0.7}
    breadth = 1.0 + 0.2 * (len(sources) - 1) + 0.05 * max(0, len(communities) - 1)
    months = set(first_month.values())     # longevity across people, not one person returning every month
    recommenders = sum(1 for w in best_by_author.values() if w >= 0.7)
    return round(base * breadth + 0.3 * len(months), 2), recommenders, sorted(months)


catalog = []
dropped_lang = []
stats = collections.Counter()
stats["inst_crosschannel_not_credited"] = cross_n
stats["inst_watchlists_dropped"] = watchlists
stats["inst_partial_playlists"] = partials
stats["quotes_withheld"] = withheld
SHELF_VIDS = {it["video"]["id"] for sh in (json.load(open(P("pipeline", "shelves.json"), encoding="utf-8"))["shelves"] if os.path.exists(P("pipeline", "shelves.json")) else []) for it in sh["items"] if it.get("video")}
# language guard (the playlist triage checked English; lectures and community videos were never checked one by one):
# a title mostly in another script, or marked as a translation, is not for an English-language catalog
NON_LATIN_RX = re.compile(r"[Ѐ-ӿ؀-ۿऀ-ॿঀ-৿਀-੿஀-௿ఀ-౿฀-๿぀-ヿ一-鿿가-힯֐-׿]")
LATIN_RX = re.compile(r"[A-Za-zÀ-ɏ]")
OTHER_LANG_RX = re.compile(r"\((spanish|español|french|français|hindi|urdu|chinese|中文|mandarin|russian|portugu[eê]s|deutsch|german|italiano|japanese|korean|arabic|turkish|polish)( version| subtitles?| audio)?\)|\b(en español|en français|em português|auf deutsch|hindi (medium|version)|versión en español|version française|subtitulado|中文版|русская версия)\b", re.I)
PROMO_RX = re.compile(r"\b(trailer|teaser|promo|tune in|coming soon|now available|announcement|announcing|channel intro|subscribe|sneak peek|save the date|registration (is )?open|register now|apply now|call for (papers|abstracts)|welcome video|course promo|preview)\b", re.I)


# Latin-script languages: function words that English does not share. A title with two or more of them, and more of them
# than English function words, is a Spanish/French/Portuguese/German/Italian title ("Módulo 6: La discapacidad en nuestra
# cultura", "McGill à vos côtés : Stades de la démence"); "Marianne La France on Gender and Emotion" is not.
OTHER_FN = set("""de la el los las en y para con del una por qué cómo sobre dentro niños personas salud cerebro su al como
le les des du pour avec dans et est une sur aux au chez vers à ce cette ses nos vos comment pourquoi entre maladie
os um uma em na dos das saúde cérebro
der und ein eine für von zu auf über nicht wie ist sind oder
il lo gli di della per che nel nella sul sulla""".split())
EN_FN = set("the a an of in on and to for with from by at is are how why what your our we you it this that as or about into than".split())


def non_english(title, desc=""):
    letters = NON_LATIN_RX.findall(title or "")
    latin = LATIN_RX.findall(title or "")
    if letters and len(letters) > 0.4 * (len(letters) + len(latin)):
        return True
    if re.match(r"\s*(?:" + NON_LATIN_RX.pattern + r"[\s　-〿，、。！？：；]*){3,}", title or ""):
        return True                        # "增強大腦的韌性 Harnessing Brain Adaptability": a bilingual title that leads with the other language is the translated version
    toks = re.findall(r"[a-zà-ÿ]+", re.sub(r"\bet al\b\.?", " ", (title or "").lower()))   # "Santos et al." is not French
    other = sum(1 for t in toks if t in OTHER_FN) + sum(0.25 for t in toks if re.search(r"[áéíóúñçàèêùôâîûäöüß]", t))   # accented names count a little, not much
    en = sum(1 for t in toks if t in EN_FN)
    if other >= 2 and other > en:
        return True
    return bool(OTHER_LANG_RX.search((title or "") + " " + (desc or "")[:200]))


for vid, rec in videos.items():
    inst = inst_member.get(vid)            # (series id, lecture index) when a university playlist carries it
    loose = inst_loose.get(vid)            # a standalone institutional talk (no series)
    course = inst_course[inst[0]] if inst else None
    m = meta.get(vid)
    if (m is None or not m.get("title")) and inst:
        m = inst_meta[vid]
    if inst and inst_meta[vid].get("p"):
        m = inst_meta[vid]
    if loose and not inst:
        inst = True                        # selection rules below treat it as institutional; course stays None
        course = {"kind": loose["kind"], "inst": loose["inst"], "unit": loose.get("unit"), "ctopics": [], "topic_map": {}, "chid": (m or {}).get("chid"), "total": 1, "ok": loose["ok"]}
    hn = rec["hn"]
    lab = hn_labels.get(vid) if hn else (new_labels.get(vid) or inst_labels.get(vid))
    if hn is None and not inst:
        if not lab or not lab.get("keep"):
            stats["dropped_not_psych_or_unlabeled"] += 1
            continue
    if inst and lab and lab.get("keep") is False and not hn:
        stats["dropped_inst_not_psych"] += 1
        continue
    if inst and not hn and not any(v["s"] != "inst" for v in rec["vouches"]) and THIRD_PARTY.search((m or {}).get("ch") or "") and (m or {}).get("chid") and m["chid"] != course.get("chid"):
        stats["dropped_inst_thirdparty"] += 1   # a CrashCourse / Khan Academy / Sprouts clip a lecturer added to their playlist is not the institution's lecture
        continue
    community_vouched = hn is not None or any(v["s"] != "inst" for v in rec["vouches"])
    if inst and not community_vouched and (m or {}).get("len") and (
            (course["kind"] == "talks" and m["len"] < 240)                                        # a 2-minute clip in a talk collection is a promo
            or m["len"] < 60                                                                       # under a minute is never a lecture
            or (m["len"] < 240 and PROMO_RX.search((m or {}).get("title") or ""))                  # "Tune in Dec. 21!", trailers, course promos
            or (lab or {}).get("promo")):                                                          # the per-lecture label says so
        stats["dropped_inst_promo"] += 1
        continue
    if m is None:
        stats["dropped_no_meta"] += 1
        continue
    if not m.get("title"):
        stats["dropped_dead"] += 1
        continue
    if m.get("live") and not m.get("len"):
        stats["dropped_live"] += 1
        continue
    if vid not in SHELF_VIDS and ((lab or {}).get("english") is False or non_english(m.get("title"), m.get("desc"))):
        stats["dropped_non_english"] += 1
        dropped_lang.append({"id": vid, "title": m.get("title"), "ch": m.get("ch")})   # work/dropped_non_english.json, for a look after each build
        continue
    comm_vouches = [v for v in rec["vouches"] if v["s"] != "inst"]
    score, _, months = score_video(rec["vouches"])
    _, nrec, _ = score_video(comm_vouches)
    pos = [v for v in comm_vouches if v["w"] >= 0.7]
    if hn is None and not inst:
        # non-HN videos need a real vouch: 2 recommenders, one upvoted mention, or an SE answer
        top_up = max((v.get("up") or 0) for v in comm_vouches)
        se_answer = any(v["s"] == "se" and v["k"] == "answer" and (v.get("up") or 0) >= 1 for v in comm_vouches)
        if nrec < 2 and top_up < 2 and not se_answer:
            stats["dropped_thin_vouch"] += 1
            continue
        # Reddit alone does not get a video in (the owner's call: not a good source, however many upvotes). Reddit mentions
        # still show as receipts on videos that are here for another reason: a Hacker News or Stack Exchange vouch, a
        # shelf, an institution.
        if not any(v["s"] in ("hn", "se") for v in comm_vouches):
            stats["dropped_reddit_only"] += 1
            continue
    topics = [t for t in (lab or {}).get("topics", []) if t in TOPIC_IDS][:3]
    if course and course.get("topic_map"):
        # a course-level correction (course_labels.jsonl "topic_map"), e.g. a statistics course filed under the wrong topic
        topics = list(dict.fromkeys(course["topic_map"].get(t, t) for t in topics))
    if not topics and course:
        topics = course["ctopics"][:3]      # no per-lecture label yet: inherit the course's topics
        stats["inst_inherited_topics"] += 1
    if not topics:
        stats["dropped_no_topic"] += 1
        continue
    contested = (lab or {}).get("contested") or ""
    if contested and contested not in CONTESTED:
        contested = ""
    vouches = sorted(comm_vouches, key=lambda v: (-v["w"], -(v.get("up") or 0)))
    # trim provenance: keep up to 12, prefer distinct communities and strong ones
    kept_v, seen_c = [], collections.Counter()
    for v in vouches:
        if seen_c[v["c"]] >= 5 and len(kept_v) >= 6:
            continue
        seen_c[v["c"]] += 1
        kept_v.append(v)
        if len(kept_v) >= 12:
            break
    src_counts = collections.Counter(v["s"] for v in comm_vouches)
    communities = collections.Counter(v["c"] for v in comm_vouches)
    clips = sorted({v["t"] for v in comm_vouches if v.get("t")})
    why = clean(hn["why_hn"], 240) if hn else ""
    summary = clean(hn["summary"], 320) if hn else clean(m.get("desc"), 240)
    if inst and not hn and not comm_vouches and re.fullmatch(r"[A-Z]{2,5}\d{3}_(Lecture|Topic)\d+", m["title"] or ""):
        summary = ""                        # "PSY409_Lecture07" descriptions are boilerplate
    dated = [v for v in comm_vouches if v.get("d")]
    first_year = min(int(v["d"][:4]) for v in dated) if dated else None
    last_year = max(int(v["d"][:4]) for v in dated) if dated else None
    kind = course["kind"] if course else None
    # a lecture is what the per-lecture label judged, not what its playlist is called: an interview show in a
    # department's "series" playlist is a talk; the playlist kind is the fallback for lectures never labeled
    is_lecture = (lab or {}).get("course") if lab and "course" in lab else kind in ("course", "series")
    entry = {
        "id": vid, "title": m["title"], "ch": m.get("ch"), "chid": m.get("chid"),
        "len": m.get("len"), "views": m.get("views"), "pub": m.get("pub"),
        "topics": topics, "area": TOPIC_AREA[topics[0]],
        "type": (hn or {}).get("content_type") or ("lecture" if is_lecture else ("talk" if inst else None)),
        "course": bool(is_lecture) if inst else bool((lab or {}).get("course")),
        "unl": bool(m.get("unl")),         # unlisted on YouTube: reachable through the playlist, not the channel page
        "score": score, "nrec": nrec, "nmention": len(comm_vouches),
        "src": dict(src_counts), "communities": [c for c, _ in communities.most_common(6)],
        "why": why, "summary": summary, "quote": clean(((hn or {}).get("quote") or {}).get("text"), 200) if hn else "",
        "vouches": [{k: v[k] for k in ("s", "c", "a", "d", "k", "q", "u", "up", "t", "thread", "why") if v.get(k) not in (None, "")} for v in kept_v],
        "badge": {"id": contested, "role": (lab or {}).get("contested_role") or "promotes"} if contested else None,
        "cw": [c for c in (lab or {}).get("cw", []) if c in TAX["content_warnings"]],
        "first": first_year, "last": last_year, "months": len(months),
        "clips": clips[:6],
        "kw": (m.get("kw") or [])[:6],
    }
    if inst and comm_vouches:
        entry["cscore"] = score_video(comm_vouches)[0]   # community-only: what the canon sorts by
    if loose and inst is True:
        entry["inst"] = {"n": loose["inst"], "loose": True}
        if loose.get("unit"):
            entry["inst"]["u"] = loose["unit"]
        if not loose["ok"]:
            entry["inst"]["ok"] = False
        entry["type"] = "lecture" if loose["kind"] == "lecture" else "talk"
        entry["course"] = False
        stats["inst_loose"] += 1
    elif inst:
        entry["inst"] = {"n": course["inst"], "i": inst[1], "of": course["total"]}   # the series id is entry["series"]
        if course.get("unit"):
            entry["inst"]["u"] = course["unit"]
        if not course.get("ok", True):
            entry["inst"]["ok"] = False    # publisher not verified: the site ranks it with other long-form, not with the institutions
            stats["inst_unverified_publisher"] += 1
        if m.get("approx"):
            entry["approx"] = True
        if m.get("p"):
            entry["p"] = m["p"]            # video provider when not YouTube ("panopto", "archive"); id is then the provider's id
            entry["host"] = m.get("host")
            if m.get("f"):
                entry["f"] = m["f"]
        if not comm_vouches:
            entry["kw"] = []
        stats["inst_lectures"] += 1
        if nrec:
            stats["inst_also_vouched"] += 1
    catalog.append(entry)
    stats["kept"] += 1

catalog.sort(key=lambda v: -v["score"])

# ---------------------------------------------------------------- replication tags (keyword candidates judged by Claude: work/replication/tags.jsonl)

rep_tags = {}
for _f in sorted(glob.glob(P("work", "replication", "tags*.jsonl"))):      # tags.jsonl (first pass) + tags_<date>.jsonl (later keyword passes)
    rep_tags.update({o["vid"]: o for o in jsonl(_f) if o.get("contested") in CONTESTED and (o.get("confidence") if o.get("confidence") is not None else 1) >= 0.6})
for v in catalog:
    t = rep_tags.get(v["id"])
    if t and not v.get("badge"):
        v["badge"] = {"id": t["contested"], "role": t.get("role") or "promotes"}
        stats["replication_tagged"] += 1

# ---------------------------------------------------------------- curated shelves (primary sources, demos)

SHELVES = json.load(open(P("pipeline", "shelves.json"), encoding="utf-8"))["shelves"] if os.path.exists(P("pipeline", "shelves.json")) else []
by_id_tmp = {v["id"]: v for v in catalog}
# the therapy shelf is curated in shelves.json and topped up from the catalog itself: psychotherapy demonstrations,
# role-plays, intake and case-formulation videos that a course or a vouched channel already brought in
THERAPY_RX = re.compile(r"role.?play|session demonstration|therapy session|full session|simulat|case (formulation|conceptuali[sz]ation|study)|motivational interviewing|clinical interview|intake and assessment|in.class therapy", re.I)
THERAPY_NEG = re.compile(r"grand rounds|conference|symposium|keynote|webinar|panel|history of|overview|promo|trailer|lecture \d|storytelling|wide circle|role of role|skills for|goal setting|gloria|what is|why |how to", re.I)
therapy_shelf = next((sh for sh in SHELVES if sh["id"] == "therapy"), None)
if therapy_shelf:
    seen_tp = {it["video"]["id"] for it in therapy_shelf["items"] if it.get("video")}
    for v in catalog:
        if v["id"] in seen_tp or (v.get("len") or 0) < 240:
            continue
        if (("therapy" in v["topics"]) or re.search(r"Beck Institute|counsel|psychotherap", (v.get("ch") or "") + " " + v["title"], re.I)) and THERAPY_RX.search(v["title"]) and not THERAPY_NEG.search(v["title"]):
            # "legit" says whose copy this is: the uploader's own channel when it is the institution that lists it, otherwise a channel's copy
            # re-listed in an institution's playlist (five Todd Grande role-plays reached the shelf through a City Vision University playlist)
            own_upload = bool(v.get("inst")) and v.get("chid") and v["chid"] in inst_channels.get(pub_key(v["inst"]["n"], v["inst"].get("u")), set())
            therapy_shelf["items"].append({"id": "tp-" + v["id"], "title": v["title"], "year": int(v["pub"][:4]) if v.get("pub") else None, "people": v.get("ch"), "what": v.get("summary") or "", "video": {"p": v.get("p") or "youtube", "id": v["id"], "uploader": v.get("ch"), "legit": "official" if own_upload else ("relisted" if v.get("inst") else "channel")}, "alt": [], "paper": None, "status": None, "topics": v["topics"][:2], "auto": True, "form": "demonstration"})
            seen_tp.add(v["id"])
shelves_out = []
for sh in SHELVES:
    items_out = []
    for it in sh["items"]:
        vd = it.get("video")
        vid = vd["id"] if vd else None
        if vid and vid not in by_id_tmp:
            m = meta.get(vid) or {}
            topics_i = [t for t in it.get("topics", []) if t in TOPIC_IDS] or ["history-of-psychology"]
            entry = {
                "id": vid, "title": m.get("title") or it["title"], "ch": m.get("ch") or vd.get("uploader", "").split(" (")[0], "chid": m.get("chid"),
                "len": m.get("len") or vd.get("len"), "views": m.get("views"), "pub": m.get("pub") or (f"{it['year']}-01-01" if it.get("year") else None),
                "topics": topics_i, "area": TOPIC_AREA[topics_i[0]],
                "type": "demo" if sh["id"] in ("demos", "therapy") else "documentary", "course": False,
                "score": 1.0, "nrec": 0, "nmention": 0, "src": {}, "communities": [],
                "why": "", "summary": clean(it.get("what"), 240), "quote": "", "vouches": [],
                "badge": None, "cw": [], "first": None, "last": None, "months": 0, "clips": [], "kw": [],
            }
            if vd["p"] != "youtube":
                entry["p"] = vd["p"]
                entry["host"] = "archive.org" if vd["p"] == "archive" else vd.get("host")
                if vd.get("f"):
                    entry["f"] = vd["f"]
            catalog.append(entry)
            by_id_tmp[vid] = entry
            stats["shelf_added"] += 1
        if vid:
            v = by_id_tmp[vid]
            v.setdefault("shelf", [])
            if sh["id"] not in v["shelf"]:
                v["shelf"].append(sh["id"])
            if "orig" not in v:                   # a video on two shelves keeps its first (richer) card
                v["orig"] = {"sid": it["id"], "shelf": sh["id"], "people": it.get("people"), "year": it.get("year"), "what": it.get("what"),
                             "paper": it.get("paper"), "paper2": it.get("paper2"), "alt": it.get("alt") or [], "uploader": vd.get("uploader"), "legit": vd.get("legit"),
                             "form": it.get("form"), "rights": vd.get("rights")}
            if it.get("status") and it["status"] in CONTESTED and not v.get("badge"):
                v["badge"] = {"id": it["status"], "role": "source"}
        items_out.append({"sid": it["id"], "vid": vid, "title": it["title"], "year": it.get("year"), "people": it.get("people"), "what": it.get("what"),
                          "paper": it.get("paper"), "paper2": it.get("paper2"), "alt": it.get("alt") or [], "status": it.get("status") if it.get("status") in CONTESTED else None,
                          "topics": [t for t in it.get("topics", []) if t in TOPIC_IDS], "legit": (vd or {}).get("legit"), "uploader": (vd or {}).get("uploader"),
                          "rights": (vd or {}).get("rights"), "form": it.get("form"), "auto": bool(it.get("auto")),
                          "p": (vd or {}).get("p"), "len": (vd or {}).get("len") or (meta.get(vid, {}).get("len") if vid else None) or (by_id_tmp[vid].get("len") if vid else None)})
    shelves_out.append({"id": sh["id"], "name": sh["name"], "short": sh.get("short") or sh["name"], "tagline": sh.get("tagline", ""), "items": items_out})
catalog.sort(key=lambda v: -v["score"])

# ---------------------------------------------------------------- related graph

by_id = {v["id"]: v for v in catalog}
related = collections.defaultdict(collections.Counter)
for vid, rel in hn_related.items():
    if vid in by_id:
        for r in rel:
            if r["vid"] in by_id:
                related[vid][r["vid"]] += 2.0 * r.get("shared_recommenders", 1)
# co-citation on Reddit / SE: same author or same thread
by_author = collections.defaultdict(set)
by_thread = collections.defaultdict(set)
for v in catalog:
    for vo in videos[v["id"]]["vouches"]:
        if vo["s"] in ("hn", "inst"):          # HN has its own related list; a playlist is not a co-recommendation
            continue
        if vo.get("a"):
            by_author[(vo["s"], vo["a"].lower())].add(v["id"])
        if vo.get("u") and vo["s"] == "reddit":
            thread = vo["u"].split("/_/")[0]
            by_thread[thread].add(v["id"])
for group, bonus in list(((s, 1.5) for s in by_author.values())) + list(((s, 1.0) for s in by_thread.values())):
    if 1 < len(group) <= 30:
        for a in group:
            for b in group:
                if a != b:
                    related[a][b] += bonus
for v in catalog:
    # ties broken by id: the co-citation groups are sets, whose iteration order changes with PYTHONHASHSEED
    v["rel"] = [r for r, _ in sorted(related[v["id"]].items(), key=lambda kv: (-kv[1], kv[0]))[:12]]

# ---------------------------------------------------------------- series (courses)

def series_key(v):
    t = v["title"]
    m = re.match(r"^\s*(\d{1,2})[.:)\-]\s+(.*)", t)
    if m and v["ch"] in ("Stanford", "YaleCourses", "MIT OpenCourseWare", "Harvard University", "UC Berkeley Events") or (m and v.get("course")):
        return v["ch"]
    m = re.search(r"(lecture|lec\.?|episode|ep\.?|part|chapter|session|#)\s*(\d{1,3})", t, re.I)
    if m and v.get("course"):
        return v["ch"]
    if v.get("course"):
        return v["ch"]
    return None


series = []
# 1) institutional courses: the playlist order is the syllabus
inst_vids = collections.defaultdict(list)
for v in catalog:
    if v.get("inst") and v["id"] in inst_member:
        inst_vids[inst_member[v["id"]][0]].append(v)
for sid, course in inst_course.items():
    vids = sorted(inst_vids.get(sid, []), key=lambda v: v["inst"]["i"])
    for v in vids:
        v["series"] = sid
    if not vids:
        continue
    topics = collections.Counter(t for v in vids for t in v["topics"])
    pop = round(sum(max(0.0, v["score"] - INST_W) for v in vids), 1)   # how much the communities vouched for its lectures
    series.append({"id": sid, "name": course["name"], "inst": course["inst"], "unit": course.get("unit"), "short": course["short"], "lecturer": course["lecturer"],
                   "affil": course.get("affil"), "verified": course.get("verified"), "ok": course.get("ok", True), "pubwhy": course.get("pubwhy"),
                   "year": course["year"], "kind": course["kind"], "level": course["level"], "note": course["note"],
                   "n": len(vids), "total": course["total"], "cross": course.get("cross", 0), "partial": course.get("partial", False), "vids": [v["id"] for v in vids],
                   "topics": (course["ctopics"] or [t for t, _ in topics.most_common(3)])[:3],
                   "vouched": sum(1 for v in vids if v["nrec"]), "pop": pop, "score": round(sum(v["score"] for v in vids), 1),
                   "url": course["url"], "ch": course["ch"], "chid": course["chid"], "provider": course["provider"], "readings": course.get("readings"),
                   "materials": course.get("materials"), "submitted": course.get("submitted"),
                   "hours": round(sum(v["len"] or 0 for v in vids) / 3600, 1)})
    for v in vids:
        v["series"] = sid
# 2) community-vouched series: several lectures of one channel recommended individually
series_members = collections.defaultdict(list)
for v in catalog:
    if v.get("series"):
        continue
    k = series_key(v)
    if k:
        series_members[k].append(v)
for ch, vids in series_members.items():
    if len(vids) < 2:
        continue
    def num(v):
        m = re.match(r"^\s*(\d{1,3})\b", v["title"]) or re.search(r"(?:lecture|lec\.?|episode|ep\.?|part|chapter|session|#)\s*(\d{1,3})", v["title"], re.I)
        return int(m.group(1)) if m else 999
    vids.sort(key=lambda v: (num(v), v.get("pub") or ""))
    topics = collections.Counter(t for v in vids for t in v["topics"])
    sid = re.sub(r"[^a-z0-9]+", "-", ch.lower()).strip("-")
    series.append({"id": sid, "name": ch, "n": len(vids), "vids": [v["id"] for v in vids], "topics": [t for t, _ in topics.most_common(3)],
                   "vouched": len(vids), "pop": round(sum(v["score"] for v in vids), 1), "score": round(sum(v["score"] for v in vids), 1),
                   "hours": round(sum(v["len"] or 0 for v in vids) / 3600, 1)})
    for v in vids:
        v["series"] = sid
KIND_ORDER = {"course": 0, "series": 1, "talks": 2}
series.sort(key=lambda s: (-s["pop"], KIND_ORDER.get(s.get("kind"), 3), -s["n"]))

# ---------------------------------------------------------------- output

topic_counts = collections.Counter(t for v in catalog for t in v["topics"])
areas_out = []
for a in TAX["areas"]:
    areas_out.append({"id": a["id"], "name": a["name"], "topics": [
        {"id": t["id"], "name": t["name"], "desc": t["description"], "n": topic_counts.get(t["id"], 0)} for t in a["topics"]]})

# ---------------------------------------------------------------- pathways (pipeline/pathways.json): ordered routes through the courses, resolved against what exists
series_ids = {sd["id"] for sd in series}
pathways_out = []
for pw in (json.load(open(P("pipeline", "pathways.json"), encoding="utf-8"))["pathways"] if os.path.exists(P("pipeline", "pathways.json")) else []):
    steps = []
    for st in pw["steps"]:
        o = {"label": st["label"], "why": st.get("why", "")}
        if st.get("all"):
            o["all"] = [sid for sid in st["all"] if sid in series_ids]
            if not o["all"]:
                continue
        elif st.get("series"):
            hit = next((sid for sid in st["series"] if sid in series_ids), None)
            if not hit:
                continue
            o["series"] = hit
        elif st.get("shelf"):
            if st["shelf"] not in {sh["id"] for sh in shelves_out}:
                continue
            o["shelf"] = st["shelf"]
        elif st.get("page"):
            o["page"] = st["page"]; o["page_label"] = st.get("page_label", st["page"])
        else:
            continue
        steps.append(o)
    if len(steps) >= 3:
        pathways_out.append({"id": pw["id"], "name": pw["name"], "for": pw.get("for", ""), "steps": steps})
stats["pathways"] = len(pathways_out)

# ---------------------------------------------------------------- content similarity (pipeline/similarity.py)
# TF-IDF cosine neighbours per video (sim: indices into videos[]) and related courses (simc: indices into series[]),
# so lectures nobody co-recommended still connect to the rest of the catalog by what they are about.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import similarity as _similarity  # noqa: E402
for _j, _sd in enumerate(series):
    _sd["_j"] = _j
stats.update(_similarity.compute(catalog, series, areas_out))
for _sd in series:
    _sd.pop("_j", None)

# SOURCE_DATE_EPOCH (reproducible-builds.org) pins the stamp so two builds of the same inputs are byte-identical
generated = dt.datetime.fromtimestamp(int(os.environ.get("SOURCE_DATE_EPOCH") or dt.datetime.now(dt.timezone.utc).timestamp()), dt.timezone.utc).strftime("%Y-%m-%d")
src_totals = collections.Counter()
for v in catalog:
    for s, n in v["src"].items():
        src_totals[s] += n
communities_total = collections.Counter(c for v in catalog for c in v["communities"])
inst_series = [s for s in series if s.get("inst")]
institutions = collections.OrderedDict()
for s in sorted(inst_series, key=lambda s: (-s["pop"], -s["n"])):
    i = institutions.setdefault(s["inst"], {"name": s["inst"], "short": s["short"], "courses": 0, "lectures": 0, "pop": 0.0, "units": []})
    i["courses"] += 1
    i["lectures"] += s["n"]
    i["pop"] = round(i["pop"] + s["pop"], 1)
    if s.get("unit") and s["unit"] not in i["units"]:
        i["units"].append(s["unit"])
    if not s.get("ok", True):
        i["unverified"] = i.get("unverified", 0) + 1
for v in catalog:                                   # standalone institutional talks count toward their institution too
    if v.get("inst") and v["inst"].get("loose"):
        i = institutions.setdefault(v["inst"]["n"], {"name": v["inst"]["n"], "short": INST_SHORT.get(v["inst"]["n"], v["inst"]["n"]), "courses": 0, "lectures": 0, "pop": 0.0, "units": []})
        i["lectures"] += 1
        i["loose"] = i.get("loose", 0) + 1
        if v["inst"].get("u") and v["inst"]["u"] not in i["units"]:
            i["units"].append(v["inst"]["u"])
for i in institutions.values():
    if i["name"] == "Independent lecturer":
        i["units"] = sorted(i["units"])             # the lecturers, alphabetically; other institutions keep their units in order of weight
vouched_videos = sum(1 for v in catalog if v["nrec"])
stats["inst_verified_lecturers"] = sum(1 for s in inst_series if s["inst"] == "Independent lecturer" and s.get("verified"))
stats["submitted_courses"] = sum(1 for s in inst_series if s.get("submitted"))
stats["inst_unverified_collections"] = sum(1 for s in inst_series if not s.get("ok", True))

data = {
    "generated": generated,
    "stats": {"videos": len(catalog), "vouched": vouched_videos, "mentions": sum(v["nmention"] for v in catalog), "sources": dict(src_totals),
              "communities": len(communities_total), "series": len(series),
              "inst": {"courses": len(inst_series), "lectures": sum(s["n"] for s in inst_series), "loose": stats.get("inst_loose", 0), "institutions": sum(1 for i in institutions.values() if i["courses"]), "institutions_all": len(institutions),
                       "also_vouched": sum(s["vouched"] for s in inst_series)}},
    "areas": areas_out,
    "contested": {k: {"name": c["name"], "note": c["note"], "source": c["source"], "status": c.get("status", "mixed"),
                      "sources": [{kk: vv for kk, vv in src.items() if vv} for src in c.get("sources", [])]} for k, c in CONTESTED.items()},
    "status_labels": TAX.get("status_labels", {}),
    "shelves": shelves_out,
    "pathways": pathways_out,
    "cw": TAX["content_warnings"],
    "institutions": list(institutions.values()),
    "inst_channels": INST_CHANNEL_IDS,      # channels the institutions publish on; a long video from one ranks as institutional even outside a pulled playlist
    "license": {
        "data": "The labels, notes, shelves, replication statuses and pathways are PsychTube's own, released under ODC-By 1.0: use them for anything, say where they came from. Video titles, channel names and lengths belong to their uploaders.",
        "hackertube": "Hacker News mentions derive from HackerTube's export (ODC-By 1.0, hackertube.org/data).",
        "stackexchange": "Stack Exchange excerpts are adaptations of CC BY-SA posts (2.5, 3.0 or 4.0 by post date); author and link are kept on each quote.",
        "reddit": "Reddit quotes are short attributed excerpts with a link to the comment; write to the repository to have one removed.",
    },
    "series": series,
    "videos": catalog,
}

EMPTY = ("", [], {}, None, 0)
for v in catalog:
    # keep the payload small: empty fields are omitted and the site restores the defaults (app.js)
    for k in [k for k, val in v.items() if val in EMPTY and k not in ("id", "title", "topics", "score")]:
        del v[k]
    if v.get("orig"):
        for k in [k for k, val in v["orig"].items() if val in EMPTY]:
            del v["orig"][k]
for s in series:
    for k in [k for k, val in s.items() if (val is None or val == "" or val is False) and k != "ok"]:   # numbers stay, even 0: the site sorts on pop and n
        del s[k]
    if s.get("ok", True):
        s.pop("ok", None)                            # only the unverified publishers carry the flag (ok: false)

os.makedirs(P("site", "data"), exist_ok=True)
# The site loads the catalog in two parts: data-core.js — everything a first page needs (the vouched videos, the shelf
# videos, each course's first lecture, the series index, institutions, notes, pathways) — and data-inst.js, the rest of
# the institutional lectures (about 90% of the rows), fetched right after the first paint. The content-neighbour indices
# (`sim`) point into the concatenation core + inst, so they are remapped here. psychtube.json stays one complete file.
import hashlib
first_of_series = {sd["vids"][0] for sd in series if sd.get("vids")}
is_core = [not v.get("inst") or v.get("nrec") or v.get("nmention") or v.get("shelf") or v.get("orig") or v["id"] in first_of_series for v in catalog]
order = [i for i, c in enumerate(is_core) if c] + [i for i, c in enumerate(is_core) if not c]
newpos = {old_i: new_i for new_i, old_i in enumerate(order)}
for v in catalog:
    if v.get("sim"):
        v["sim"] = [newpos[i] for i in v["sim"]]
core_videos = [catalog[i] for i in order if is_core[i]]
inst_videos = [catalog[i] for i in order if not is_core[i]]
data["videos"] = core_videos + inst_videos                        # the export keeps the same order as the two files together
inst_blob = json.dumps({"videos": inst_videos}, ensure_ascii=False, separators=(",", ":"))
inst_hash = hashlib.sha1(inst_blob.encode("utf-8")).hexdigest()[:10]
core = dict(data, videos=core_videos, inst_file="data-inst.js", v=inst_hash, inst_count=len(inst_videos))
with open(P("site", "data-core.js"), "w", encoding="utf-8") as f:
    f.write("window.PT = ")
    json.dump(core, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")
with open(P("site", "data-inst.js"), "w", encoding="utf-8") as f:
    f.write("window.PT_INST = " + inst_blob + ";\n")
if os.path.exists(P("site", "data.js")):
    os.remove(P("site", "data.js"))                               # replaced by the two parts
with open(P("site", "data", "psychtube.json"), "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)
stats["core_videos"] = len(core_videos)
stats["inst_part_videos"] = len(inst_videos)
with open(P("work", "inst", "crosschannel.json"), "w", encoding="utf-8") as f:   # review list for triage_overrides.json → affiliated_channels
    json.dump([{"inst": i, "channel": ch, "items": n} for (i, ch), n in cross_review.most_common()], f, ensure_ascii=False, indent=1)
with open(P("work", "dropped_non_english.json"), "w", encoding="utf-8") as f:
    json.dump(dropped_lang, f, ensure_ascii=False, indent=1)
with open(P("work", "catalog_stats.json"), "w") as f:
    json.dump({"stats": dict(stats), "topics": topic_counts.most_common(), "sources": dict(src_totals),
               "communities": communities_total.most_common(40), "series": [(s["name"], s["n"]) for s in series]}, f, indent=1)

print("catalog:", len(catalog), "videos;", dict(stats))
print("sources:", dict(src_totals))
print("institutional:", data["stats"]["inst"])
print("series:", [(s["name"], s["n"]) for s in series[:12]])
print("top topics:", topic_counts.most_common(12))
print("size:", os.path.getsize(P("site", "data-core.js")) // 1024, "KB core +", os.path.getsize(P("site", "data-inst.js")) // 1024, "KB institutional part;", len(core_videos), "core videos")
