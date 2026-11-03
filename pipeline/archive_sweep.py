#!/usr/bin/env python3
"""Internet Archive sweep for institutional lecture collections (runs in the archive workflow; the build machine cannot
reach archive.org). UC Berkeley's 2005–2015 webcasts (removed from YouTube in 2017) are the big one: one item per lecture,
`ucberkeley_webcast_<original YouTube id>`.

    python3 pipeline/archive_sweep.py list                      -> work/archive/items_<collection>.json  (every item: identifier,
                                                                   title, description, date, subject, runtime)
    python3 pipeline/archive_sweep.py files work/archive/want.json
                                                                -> work/archive/files.json  {identifier: {"file", "length", "size",
                                                                   "date", "description"}} for the items listed in want.json

The advancedsearch API is public and meant for this (one request per 5,000 rows); the per-item metadata calls are one
request each, paced. Selection into courses happens on the build machine (pipeline/archive_courses.py).
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
UA = "PsychTube archive sweep (github.com/contofalskyR/PsychTube; paced, one request at a time)"
COLLECTIONS = ["ucberkeley-webcast"]


def get_json(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:                   # noqa: BLE001
            print("retry", i + 1, url[:120], e, file=sys.stderr)
            time.sleep(3 * (i + 1))
    return None


def list_items():
    """The scrape API (cursor-paged) rather than advancedsearch, whose paging stops at 10,000 rows."""
    os.makedirs(P("work", "archive"), exist_ok=True)
    for coll in COLLECTIONS:
        rows, cursor = [], None
        while True:
            params = {"q": f"collection:{coll}", "fields": "identifier,title,description,date,subject,runtime,creator", "count": 10000}
            if cursor:
                params["cursor"] = cursor
            d = get_json(f"https://archive.org/services/search/v1/scrape?{urllib.parse.urlencode(params)}")
            if not d:
                break
            docs = d.get("items", [])
            rows.extend(docs)
            print(f"{coll}: {len(rows)}/{d.get('total')}", flush=True)
            cursor = d.get("cursor")
            if not cursor or not docs:
                break
            time.sleep(1.0)
        json.dump(rows, open(P("work", "archive", f"items_{coll}.json"), "w", encoding="utf-8"), ensure_ascii=False)
        print(f"{coll}: {len(rows)} items -> work/archive/items_{coll}.json")


def files(want_path):
    want = json.load(open(want_path, encoding="utf-8"))          # [identifier, ...]
    out_path = P("work", "archive", "files.json")
    out = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
    for i, ident in enumerate(want):
        if ident in out:
            continue
        d = get_json(f"https://archive.org/metadata/{ident}")
        if not d:
            out[ident] = {"error": "no metadata"}
            continue
        md = d.get("metadata", {}) or {}
        best = None
        for f in d.get("files", []) or []:
            name = f.get("name", "")
            if not re.search(r"\.(mp4|m4v|mov|ogv|mkv)$", name, re.I):
                continue
            size = int(f.get("size") or 0)
            # prefer the original/derivative h.264 mp4 of reasonable size; archive 'length' is seconds as a string
            score = (0 if f.get("source") == "original" else 1, -size)
            if best is None or score < best[0]:
                best = (score, f)
        rec = {"date": md.get("date"), "description": md.get("description") if isinstance(md.get("description"), str) else " ".join(md.get("description") or []),
               "title": md.get("title"), "runtime": md.get("runtime")}
        if best:
            f = best[1]
            rec.update({"file": f.get("name"), "length": float(f["length"]) if str(f.get("length") or "").replace(".", "", 1).isdigit() else None, "size": int(f.get("size") or 0)})
        out[ident] = rec
        if (i + 1) % 50 == 0:
            json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
            print(f"{i + 1}/{len(want)}", flush=True)
        time.sleep(0.4)
    json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(out)} items with file metadata -> work/archive/files.json")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        list_items()
    elif len(sys.argv) > 2 and sys.argv[1] == "files":
        files(sys.argv[2])
    else:
        sys.exit(__doc__)
