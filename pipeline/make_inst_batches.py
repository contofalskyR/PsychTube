#!/usr/bin/env python3
"""Prepare labeling inputs for the institutional tier (university courses and lecture collections).

Reads  raw/institutional/courses.json   (playlists pulled from university / lecturer channels)
       raw/youtube/meta_*.json          (YouTube metadata; descriptions help the labeler)
Writes work/inst/courses_in.jsonl       one row per playlist  -> label with INSTRUCTIONS_courses.md
       work/inst/batch_NN.jsonl         one row per video     -> label with INSTRUCTIONS_institutional.md
       (courses that already have a line in work/inst/course_labels.jsonl and videos that already have a line in
       work/inst/out_*.jsonl are skipped, so re-running after adding playlists only emits the new work)

Usage: python3 pipeline/make_inst_batches.py [batch_size] [--only-mixed] [--label-big N]
       --only-mixed   skip lectures of courses whose card says per_video_topics=false (they inherit the course topics)
       --label-big N  but still queue those lectures when the course has more than N of them (a 40-lecture course
                      filed under one topic hides lectures on others; the review found inherited labels wrong twice
                      as often as judged ones)
"""
import glob
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
size = int(args[0]) if args else 150


def jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()] if os.path.exists(path) else []


courses = json.load(open(P("raw", "institutional", "courses.json")))["courses"]
meta = {}
for f in sorted(glob.glob(P("raw", "youtube", "meta_*.json"))):
    meta.update(json.load(open(f)))
labeled = set()
for f in glob.glob(P("work", "inst", "out_*.jsonl")):
    labeled |= {o["vid"] for o in jsonl(f)}
labeled_courses = {o["pid"] for o in jsonl(P("work", "inst", "course_labels.jsonl"))}   # course cards already written

os.makedirs(P("work", "inst"), exist_ok=True)
new_courses = [c for c in courses if c["pid"] not in labeled_courses]
if new_courses:                       # leave the previous round's input in place when there is nothing new
  with open(P("work", "inst", "courses_in.jsonl"), "w", encoding="utf-8") as f:
    for c in new_courses:
        f.write(json.dumps({
            "pid": c["pid"], "inst": c["inst"], "kind": c["kind"], "playlist_title": c["title"], "channel": c.get("owner"),
            "n_videos": c["n"], "description": (c.get("desc") or "")[:600],
            "sample_titles": [it["title"] for it in c["items"][:10]],
            "typical_length_min": round(sorted(it["len"] or 0 for it in c["items"])[len(c["items"]) // 2] / 60) if c["items"] else None,
        }, ensure_ascii=False) + "\n")

only_mixed = "--only-mixed" in sys.argv      # per-lecture labels only where the course card says the lectures span topics
label_big = int(sys.argv[sys.argv.index("--label-big") + 1]) if "--label-big" in sys.argv else None
card = {o["pid"]: o for o in jsonl(P("work", "inst", "course_labels.jsonl"))}
rows = []
seen = set()
for c in courses:
    cl = card.get(c["pid"])
    if cl is not None and cl.get("keep") is False:
        continue                                              # the card dropped the whole playlist
    if only_mixed and cl is not None and cl.get("per_video_topics") is False and not (label_big is not None and c["n"] > label_big):
        continue                                              # lectures inherit the course topics
    for it in c["items"]:
        vid = it["id"]
        if vid in seen or vid in labeled or it["title"] in ("[Private video]", "[Deleted video]"):
            continue
        seen.add(vid)
        m = meta.get(vid) or {}
        rows.append({
            "vid": vid, "title": m.get("title") or it["title"], "channel": m.get("ch") or it.get("ch"),
            "playlist": c["title"], "institution": c["inst"], "position": f"{it['idx']}/{c['n']}",
            "duration_s": m.get("len") or it.get("len"), "yt_category": m.get("cat"), "yt_keywords": (m.get("kw") or [])[:8],
            "description": (m.get("desc") or "")[:300],
        })

# standalone institutional talks (raw/institutional/loose.json) are labeled like any lecture
loose_path = P("raw", "institutional", "loose.json")
if os.path.exists(loose_path):
    for lv in json.load(open(loose_path, encoding="utf-8"))["videos"]:
        vid = lv["id"]
        if vid in seen or vid in labeled:
            continue
        seen.add(vid)
        m = meta.get(vid) or {}
        rows.append({
            "vid": vid, "title": m.get("title") or vid, "channel": m.get("ch") or lv.get("ch"),
            "playlist": "(standalone video, no playlist)", "institution": lv["inst"], "position": "1/1",
            "duration_s": m.get("len"), "yt_category": m.get("cat"), "yt_keywords": (m.get("kw") or [])[:8],
            "description": (m.get("desc") or "")[:300],
        })

# number new batches after the highest out_NN already written, so outputs never collide with earlier rounds
import re
done_idx = [int(m.group(1)) for f in glob.glob(P("work", "inst", "out_*.jsonl")) for m in [re.search(r"out_(\d+)\.jsonl$", f)] if m]
first = max(done_idx) + 1 if done_idx else 0
for f in glob.glob(P("work", "inst", "batch_*.jsonl")):      # unanswered inputs from an earlier run (answered ones stay as the record of what was labeled)
    m = re.search(r"batch_(\d+)\.jsonl$", f)
    if m and int(m.group(1)) not in done_idx:
        os.remove(f)
n = math.ceil(len(rows) / size) if rows else 0
for i in range(n):
    with open(P("work", "inst", f"batch_{first + i:02d}.jsonl"), "w", encoding="utf-8") as f:
        for r in rows[i * size:(i + 1) * size]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"{len(new_courses)} of {len(courses)} courses still need a course card -> work/inst/courses_in.jsonl; {len(rows)} unlabeled videos -> {n} batches (work/inst/batch_{first:02d}.jsonl…)")
