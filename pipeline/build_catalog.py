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
    return dt.datetime.utcfromtimestamp(epoch).strftime("%Y-%m")


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
    w = (1.0 if sc >= 1 else 0.3) * (1.0 + min(max(sc, 0), 50) ** 0.5 * 0.08)
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
inst_file = P("raw", "institutional", "courses.json")
inst_courses = json.load(open(inst_file))["courses"] if os.path.exists(inst_file) else []
course_labels = {o["pid"]: o for o in jsonl(P("work", "inst", "course_labels.jsonl"))}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def approx_views(info):
    m = re.match(r"\s*([\d.,]+)\s*([KMB]?)", info or "")
    if not m:
        return None
    n = float(m.group(1).replace(",", "")) * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9}[m.group(2)]
    return int(n)


def approx_pub(info):
    m = re.search(r"(\d+)\s*(y|mo|w|d|h)\b", info or "")
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2)
    now = dt.datetime.utcnow()
    years = n if unit == "y" else 0
    return f"{now.year - years:04d}-01-01" if unit == "y" else now.strftime("%Y-%m-01")


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
    inst_course[sid] = {
        "id": sid, "name": name, "inst": c["inst"], "short": INST_SHORT.get(c["inst"], c["inst"]), "provider": c.get("provider") or "youtube",
        "lecturer": cl.get("lecturer") or "", "year": cl.get("year"), "kind": cl.get("kind") or c["kind"],
        "level": cl.get("level") or "", "note": clean(cl.get("note"), 200), "ctopics": [t for t in cl.get("topics", []) if t in TOPIC_IDS],
        "pid": c["pid"], "url": c.get("url") or f"https://www.youtube.com/playlist?list={c['pid']}", "ch": c.get("owner"), "chid": c.get("ownerId"),
        "total": len(items), "items": items, "topic_map": cl.get("topic_map") or {},
    }
    for it in items:
        vid = it["id"]
        if vid in inst_member:
            continue  # first course wins when a video sits in two playlists
        inst_member[vid] = (sid, it["idx"])
        inst_meta[vid] = {"title": it["title"], "ch": it.get("ch") or c.get("owner"), "chid": it.get("chid") or c.get("ownerId"),
                          "len": it.get("len"), "views": approx_views(it.get("info")), "pub": it.get("pub") or approx_pub(it.get("info")),
                          "approx": not c.get("provider")}
        if c.get("provider"):           # not YouTube (e.g. a university's Panopto): the site needs the host to embed and link
            inst_meta[vid]["p"] = c["provider"]
            inst_meta[vid]["host"] = c.get("host")
            if it.get("file"):
                inst_meta[vid]["f"] = it["file"]   # Internet Archive: the MP4 file name, so the site can use its own <video> player
        videos[vid]["vouches"].append({
            "s": "inst", "c": c["inst"], "a": c.get("owner"), "d": None, "k": "course", "w": INST_W,
            "q": f"Lecture {it['idx']} of {len(items)} in {name}", "u": c.get("url") or f"https://www.youtube.com/playlist?list={c['pid']}",
            "up": None, "thread": None, "t": None,
        })

# ---------------------------------------------------------------- score + select

def score_video(vouches):
    """distinct-voucher weighted sum, with a breadth bonus across communities."""
    best_by_author = {}
    extra = 0.0
    for v in vouches:
        key = (v["s"], (v.get("a") or "?").lower())
        if key in best_by_author:
            extra += 0.15 * v["w"]
            best_by_author[key] = max(best_by_author[key], v["w"])
        else:
            best_by_author[key] = v["w"]
    base = sum(best_by_author.values()) + extra
    communities = {v["c"] for v in vouches if v["w"] >= 0.7}
    sources = {v["s"] for v in vouches if v["w"] >= 0.7}
    breadth = 1.0 + 0.2 * (len(sources) - 1) + 0.05 * max(0, len(communities) - 1)
    months = {v["d"] for v in vouches if v["w"] >= 0.7 and v.get("d")}
    recommenders = sum(1 for w in best_by_author.values() if w >= 0.7)
    return round(base * breadth + 0.3 * len(months), 2), recommenders, sorted(months)


catalog = []
stats = collections.Counter()
for vid, rec in videos.items():
    inst = inst_member.get(vid)            # (series id, lecture index) when a university playlist carries it
    course = inst_course[inst[0]] if inst else None
    m = meta.get(vid)
    if (m is None or not m.get("title")) and inst:
        m = inst_meta[vid]
    if inst and inst_meta[vid].get("p"):
        m = inst_meta[vid]
    hn = rec["hn"]
    lab = hn_labels.get(vid) if hn else (new_labels.get(vid) or inst_labels.get(vid))
    if hn is None and not inst:
        if not lab or not lab.get("keep"):
            stats["dropped_not_psych_or_unlabeled"] += 1
            continue
    if inst and lab and lab.get("keep") is False and not hn:
        stats["dropped_inst_not_psych"] += 1
        continue
    if inst and course["kind"] == "talks" and not hn and not any(v["s"] != "inst" for v in rec["vouches"]) and (m or {}).get("len") and m["len"] < 240:
        stats["dropped_inst_promo"] += 1       # a 2-minute clip in a university talk collection is a promo, not a lecture
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
    entry = {
        "id": vid, "title": m["title"], "ch": m.get("ch"), "chid": m.get("chid"),
        "len": m.get("len"), "views": m.get("views"), "pub": m.get("pub"),
        "topics": topics, "area": TOPIC_AREA[topics[0]],
        "type": (hn or {}).get("content_type") or ("lecture" if ((lab or {}).get("course") or kind in ("course", "series")) else ("talk" if inst else None)),
        "course": bool((lab or {}).get("course")) or kind in ("course", "series"),
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
    if inst:
        entry["inst"] = {"n": course["inst"], "i": inst[1], "of": course["total"]}   # the series id is entry["series"]
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
        if vo["s"] == "hn":
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
    v["rel"] = [r for r, _ in related[v["id"]].most_common(12)]

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
    if v.get("inst"):
        inst_vids[inst_member[v["id"]][0]].append(v)
for sid, course in inst_course.items():
    vids = sorted(inst_vids.get(sid, []), key=lambda v: v["inst"]["i"])
    for v in vids:
        v["series"] = sid
    if not vids:
        continue
    topics = collections.Counter(t for v in vids for t in v["topics"])
    pop = round(sum(max(0.0, v["score"] - INST_W) for v in vids), 1)   # how much the communities vouched for its lectures
    series.append({"id": sid, "name": course["name"], "inst": course["inst"], "short": course["short"], "lecturer": course["lecturer"],
                   "year": course["year"], "kind": course["kind"], "level": course["level"], "note": course["note"],
                   "n": len(vids), "total": course["total"], "vids": [v["id"] for v in vids],
                   "topics": (course["ctopics"] or [t for t, _ in topics.most_common(3)])[:3],
                   "vouched": sum(1 for v in vids if v["nrec"]), "pop": pop, "score": round(sum(v["score"] for v in vids), 1),
                   "url": course["url"], "ch": course["ch"], "chid": course["chid"], "provider": course["provider"],
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

generated = dt.datetime.utcnow().strftime("%Y-%m-%d")
src_totals = collections.Counter()
for v in catalog:
    for s, n in v["src"].items():
        src_totals[s] += n
communities_total = collections.Counter(c for v in catalog for c in v["communities"])
inst_series = [s for s in series if s.get("inst")]
institutions = collections.OrderedDict()
for s in sorted(inst_series, key=lambda s: (-s["pop"], -s["n"])):
    i = institutions.setdefault(s["inst"], {"name": s["inst"], "short": s["short"], "courses": 0, "lectures": 0, "pop": 0.0})
    i["courses"] += 1
    i["lectures"] += s["n"]
    i["pop"] = round(i["pop"] + s["pop"], 1)
vouched_videos = sum(1 for v in catalog if v["nrec"])

data = {
    "generated": generated,
    "stats": {"videos": len(catalog), "vouched": vouched_videos, "mentions": sum(v["nmention"] for v in catalog), "sources": dict(src_totals),
              "communities": len(communities_total), "series": len(series),
              "inst": {"courses": len(inst_series), "lectures": sum(s["n"] for s in inst_series), "institutions": len(institutions),
                       "also_vouched": sum(s["vouched"] for s in inst_series)}},
    "areas": areas_out,
    "contested": {k: {"name": c["name"], "note": c["note"], "source": c["source"]} for k, c in CONTESTED.items()},
    "cw": TAX["content_warnings"],
    "institutions": list(institutions.values()),
    "series": series,
    "videos": catalog,
}

EMPTY = ("", [], {}, None, 0)
for v in catalog:
    # keep the payload small: empty fields are omitted and the site restores the defaults (app.js)
    for k in [k for k, val in v.items() if val in EMPTY and k not in ("id", "title", "topics", "score")]:
        del v[k]

os.makedirs(P("site", "data"), exist_ok=True)
with open(P("site", "data.js"), "w", encoding="utf-8") as f:
    f.write("window.PT = ")
    json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")
with open(P("site", "data", "psychtube.json"), "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)
with open(P("work", "catalog_stats.json"), "w") as f:
    json.dump({"stats": dict(stats), "topics": topic_counts.most_common(), "sources": dict(src_totals),
               "communities": communities_total.most_common(40), "series": [(s["name"], s["n"]) for s in series]}, f, indent=1)

print("catalog:", len(catalog), "videos;", dict(stats))
print("sources:", dict(src_totals))
print("institutional:", data["stats"]["inst"])
print("series:", [(s["name"], s["n"]) for s in series[:12]])
print("top topics:", topic_counts.most_common(12))
print("size:", os.path.getsize(P("site", "data.js")) // 1024, "KB")
