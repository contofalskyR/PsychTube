#!/usr/bin/env python3
"""Refresh YouTube metadata for every video in the catalog with the YouTube Data API v3.

Usage:  YOUTUBE_API_KEY=... python3 pipeline/fetch_youtube_meta.py
Writes: raw/youtube/meta_api.json  (same shape as the keyless snapshots: {vid: {...}})
Then:   python3 pipeline/build_catalog.py

Standard library only. 50 ids per request = 1 quota unit; a 1,500-video catalog is ~30 units.
"""
import glob
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
key = os.environ.get("YOUTUBE_API_KEY")
if not key:
    sys.exit("set YOUTUBE_API_KEY (see README: 5 minutes in Google Cloud, free)")

vids = set()
for f in glob.glob(os.path.join(ROOT, "raw", "youtube", "meta_*.json")):
    vids |= set(json.load(open(f)).keys())
cat = os.path.join(ROOT, "site", "data", "psychtube.json")
if os.path.exists(cat):
    vids |= {v["id"] for v in json.load(open(cat))["videos"]}
vids = sorted(vids)


def iso_dur(s):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return None
    d, h, mi, se = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


out = {}
for i in range(0, len(vids), 50):
    ids = vids[i:i + 50]
    q = urllib.parse.urlencode({"part": "snippet,contentDetails,statistics,status", "id": ",".join(ids), "key": key, "maxResults": 50})
    with urllib.request.urlopen(f"https://www.googleapis.com/youtube/v3/videos?{q}") as r:
        items = json.load(r).get("items", [])
    got = {it["id"]: it for it in items}
    for v in ids:
        it = got.get(v)
        if not it:
            out[v] = {"id": v, "st": "ERROR"}  # deleted or private
            continue
        sn, cd, st, stat = it.get("snippet", {}), it.get("contentDetails", {}), it.get("status", {}), it.get("statistics", {})
        out[v] = {"id": v, "st": "OK", "title": sn.get("title"), "ch": sn.get("channelTitle"), "chid": sn.get("channelId"),
                  "len": iso_dur(cd.get("duration")), "views": int(stat["viewCount"]) if stat.get("viewCount") else None,
                  "live": sn.get("liveBroadcastContent") not in (None, "none"), "pub": (sn.get("publishedAt") or "")[:10] or None,
                  "cat": None, "kw": (sn.get("tags") or [])[:10], "desc": (sn.get("description") or "")[:300],
                  "emb": st.get("embeddable"), "unl": st.get("privacyStatus") == "unlisted"}
    print(f"{min(i + 50, len(vids))}/{len(vids)}", end="\r", flush=True)
    time.sleep(0.2)

os.makedirs(os.path.join(ROOT, "raw", "youtube"), exist_ok=True)
with open(os.path.join(ROOT, "raw", "youtube", "meta_api.json"), "w") as f:
    json.dump(out, f)
print(f"\nwrote {len(out)} records to raw/youtube/meta_api.json; now run pipeline/build_catalog.py")
