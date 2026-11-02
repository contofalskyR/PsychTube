#!/usr/bin/env python3
"""Prepare labeling inputs for the institutional tier (university courses and lecture collections).

Reads  raw/institutional/courses.json   (playlists pulled from university / lecturer channels)
       raw/youtube/meta_*.json          (YouTube metadata; descriptions help the labeler)
Writes work/inst/courses_in.jsonl       one row per playlist  -> label with INSTRUCTIONS_courses.md
       work/inst/batch_NN.jsonl         one row per video     -> label with INSTRUCTIONS_institutional.md
       (videos that already have a line in work/inst/out_*.jsonl are skipped)

Usage: python3 pipeline/make_inst_batches.py [batch_size]
"""
import glob
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
size = int(sys.argv[1]) if len(sys.argv) > 1 else 150


def jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()] if os.path.exists(path) else []


courses = json.load(open(P("raw", "institutional", "courses.json")))["courses"]
meta = {}
for f in sorted(glob.glob(P("raw", "youtube", "meta_*.json"))):
    meta.update(json.load(open(f)))
labeled = set()
for f in glob.glob(P("work", "inst", "out_*.jsonl")):
    labeled |= {o["vid"] for o in jsonl(f)}

os.makedirs(P("work", "inst"), exist_ok=True)
with open(P("work", "inst", "courses_in.jsonl"), "w", encoding="utf-8") as f:
    for c in courses:
        f.write(json.dumps({
            "pid": c["pid"], "inst": c["inst"], "kind": c["kind"], "playlist_title": c["title"], "channel": c.get("owner"),
            "n_videos": c["n"], "description": (c.get("desc") or "")[:600],
            "sample_titles": [it["title"] for it in c["items"][:10]],
            "typical_length_min": round(sorted(it["len"] or 0 for it in c["items"])[len(c["items"]) // 2] / 60) if c["items"] else None,
        }, ensure_ascii=False) + "\n")

rows = []
seen = set()
for c in courses:
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

n = math.ceil(len(rows) / size) if rows else 0
for i in range(n):
    with open(P("work", "inst", f"batch_{i:02d}.jsonl"), "w", encoding="utf-8") as f:
        for r in rows[i * size:(i + 1) * size]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"{len(courses)} courses -> work/inst/courses_in.jsonl; {len(rows)} unlabeled videos -> {n} batches (work/inst/batch_NN.jsonl)")
