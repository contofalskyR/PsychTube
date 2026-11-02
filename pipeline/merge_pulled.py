#!/usr/bin/env python3
"""Append pulled playlists to raw/institutional/courses.json.

Reads  work/triage/out_*.jsonl            triage decisions (keep, inst, kind, english, confidence)
       <pulled.json>                      {pid: {title, desc, count, owner, ownerId, items:[{id,title,len,idx,ch,chid,info}]}}
                                          as window.__playlistFull() returns it (pipeline/NOTES.md)
Writes raw/institutional/courses.json     with one new course per kept, non-empty, not-yet-present playlist

Usage: python3 pipeline/merge_pulled.py raw/institutional/pulled_<date>.json [--min-items 3]
Prints what was added and what was skipped (already present, too short, unavailable).
"""
import datetime
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

if len(sys.argv) < 2:
    sys.exit(__doc__)
src = sys.argv[1]
min_items = int(sys.argv[sys.argv.index("--min-items") + 1]) if "--min-items" in sys.argv else 3

triage = {}
for f in sorted(glob.glob(P("work", "triage", "out_*.jsonl"))):
    for line in open(f, encoding="utf-8"):
        line = line.strip()
        if line:
            o = json.loads(line)
            triage[o["pid"]] = o

ov = json.load(open(P("pipeline", "triage_overrides.json"), encoding="utf-8")) if os.path.exists(P("pipeline", "triage_overrides.json")) else {}
drop_inst, drop_pid, rename = set(ov.get("drop_inst", [])), set(ov.get("drop_pid", [])), ov.get("rename_inst", {})
pulled = json.load(open(src, encoding="utf-8"))
cj = json.load(open(P("raw", "institutional", "courses.json"), encoding="utf-8"))
have = {c["pid"] for c in cj["courses"]}
have_vids = {it["id"] for c in cj["courses"] for it in c["items"]}

added, skipped = [], []
for pid, pl in pulled.items():
    t = triage.get(pid)
    if pid in have:
        skipped.append((pid, "already present")); continue
    if not t or not t.get("keep"):
        skipped.append((pid, "not kept by triage")); continue
    if pid in drop_pid or (t.get("inst") in drop_inst):
        skipped.append((pid, "dropped by triage_overrides")); continue
    inst = rename.get(t.get("inst"), t.get("inst")) or "Independent lecturer"
    items = [it for it in (pl.get("items") or []) if it.get("id")]
    if len(items) < min_items:
        skipped.append((pid, f"only {len(items)} items")); continue
    for i, it in enumerate(items, 1):
        it.setdefault("idx", i)
    overlap = sum(1 for it in items if it["id"] in have_vids) / len(items)
    if overlap >= 0.6:                                   # the same lectures under another playlist (mirror, "best of", re-listing)
        skipped.append((pid, "duplicate of a course already in")); continue
    cj["courses"].append({
        "pid": pid, "title": pl.get("title") or "", "desc": pl.get("desc") or "", "count": pl.get("count") or f"{len(items)} videos",
        "owner": pl.get("owner") or (items[0].get("ch") if items else ""), "ownerId": pl.get("ownerId") or (items[0].get("chid") if items else ""),
        "n": len(items), "items": items, "inst": inst, "kind": t.get("kind") or "course",
        "triage": {"confidence": t.get("confidence"), "why": t.get("why")},
    })
    have.add(pid)
    have_vids |= {it["id"] for it in items}
    added.append((pid, inst, len(items), pl.get("title")))

cj["pulled"] = datetime.date.today().isoformat()
json.dump(cj, open(P("raw", "institutional", "courses.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=None, separators=(",", ":"))
print(f"added {len(added)} playlists ({sum(a[2] for a in added)} lectures); skipped {len(skipped)}")
for pid, inst, n, title in added:
    print(f"  + {pid}  {inst}: {title} ({n})")
from collections import Counter
print("  skipped:", dict(Counter(r for _, r in skipped)))
