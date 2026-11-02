#!/usr/bin/env python3
"""Create classification batches for videos that have YouTube metadata but no label yet.

Usage:  python3 pipeline/make_batches.py [batch_size]
Writes: work/classify_new/batch_<tag>_NN.jsonl  (one row per unlabeled, alive video, with the
        community contexts that linked it). Have a model fill in out_<tag>_NN.jsonl following
        work/classify_new/INSTRUCTIONS.md, then run pipeline/build_catalog.py.
"""
import collections
import glob
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
size = int(sys.argv[1]) if len(sys.argv) > 1 else 120


def jsonl(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()] if os.path.exists(path) else []


labeled = set()
for f in glob.glob(P("work", "classify", "out_*.jsonl")) + glob.glob(P("work", "classify_new", "out_*.jsonl")):
    labeled |= {o["vid"] for o in jsonl(f)}
meta = {}
for f in sorted(glob.glob(P("raw", "youtube", "meta_*.json"))):
    meta.update(json.load(open(f)))

ctx = collections.defaultdict(list)
se_path = P("raw", "stackexchange", "psychology_se.json")
if os.path.exists(se_path):
    se = json.load(open(se_path))
    for p in se.get("posts", []) + se.get("comments", []):
        for v in p["v"]:
            ctx[v["id"]].append({"source": "Psych SE", "kind": p["k"], "score": p.get("sc"), "thread": p.get("title"), "snippet": (p.get("b") or "")[:300]})
for f in sorted(glob.glob(P("raw", "reddit", "reddit_*.json"))):
    d = json.load(open(f))
    for r in d.get("records", []):
        for v in r["v"]:
            ctx[v["id"]].append({"source": "r/" + r["s"], "kind": "comment", "score": r.get("sc"), "snippet": (r.get("b") or "")[:300]})
    for p in d.get("posts", []):
        for v in p["v"]:
            ctx[v["id"]].append({"source": "r/" + p["s"], "kind": "post", "score": p.get("sc"), "thread": p.get("ti"), "snippet": (p.get("st") or "")[:300]})

rows = []
for vid, c in ctx.items():
    m = meta.get(vid)
    if vid in labeled or not m or not m.get("title"):
        continue
    c.sort(key=lambda x: -(x.get("score") or 0))
    rows.append({"vid": vid, "title": m["title"], "channel": m.get("ch"), "duration_s": m.get("len"), "views": m.get("views"),
                 "yt_category": m.get("cat"), "yt_keywords": m.get("kw"), "description": (m.get("desc") or "")[:300], "contexts": c[:3]})

tag = time.strftime("%m%d%H%M")
os.makedirs(P("work", "classify_new"), exist_ok=True)
n = math.ceil(len(rows) / size) if rows else 0
for i in range(n):
    with open(P("work", "classify_new", f"batch_{tag}_{i:02d}.jsonl"), "w", encoding="utf-8") as f:
        for r in rows[i * size:(i + 1) * size]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"{len(rows)} unlabeled videos -> {n} batches (work/classify_new/batch_{tag}_NN.jsonl)")
