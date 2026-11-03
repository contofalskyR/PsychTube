#!/usr/bin/env python3
"""Apply a Data API refresh (work/yt_api/refresh_<date>.json, from `yt_api.py refresh`) to raw/institutional/courses.json.

    python3 pipeline/apply_refresh.py work/yt_api/refresh_2026-12-01.json

- lectures that left a playlist are marked `gone: <date>` (kept in the record so links and progress survive; the build
  leaves them out of the catalog and the course page says how many were removed);
- lectures new to a playlist are appended with their position, `pub` unknown until the next metadata pull, and go through
  make_inst_batches.py for labels like any other;
- playlists that are gone or private are marked `gone` on the course; the build drops the course and the About page's
  "removed" count grows.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)


def main():
    ref = json.load(open(sys.argv[1], encoding="utf-8"))
    date = ref["date"]
    cj = json.load(open(P("raw", "institutional", "courses.json"), encoding="utf-8"))
    by = {c["pid"]: c for c in cj["courses"]}
    added = removed = 0
    for pid, d in ref["courses"].items():
        c = by.get(pid)
        if not c:
            continue
        have = {it["id"] for it in c["items"]}
        for g in d["gone"]:
            for it in c["items"]:
                if it["id"] == g and not it.get("gone"):
                    it["gone"] = date; removed += 1
        for n in d["new"]:
            if n["id"] not in have:
                c["items"].append({"id": n["id"], "title": n["title"], "len": None, "idx": n["idx"], "ch": n.get("ch") or c.get("owner"), "chid": n.get("chid") or c.get("ownerId"), "info": "", "added": date})
                added += 1
        for r in d["retitled"]:
            for it in c["items"]:
                if it["id"] == r["id"]:
                    it["title"] = r["now"]
        c["items"].sort(key=lambda it: it.get("idx", 0))
        c["n"] = sum(1 for it in c["items"] if not it.get("gone"))
        c["refreshed"] = date
    for pid in ref["gone_playlists"]:
        if pid in by and not by[pid].get("gone"):
            by[pid]["gone"] = date
    json.dump(cj, open(P("raw", "institutional", "courses.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{added} lectures added, {removed} marked gone, {len(ref['gone_playlists'])} playlists gone; next: python3 pipeline/make_inst_batches.py 150 --only-mixed --label-big 10, label, build")


if __name__ == "__main__":
    main()
