#!/usr/bin/env python3
"""YouTube Data API v3 pulls — the sanctioned, quota-metered route, so the sweep no longer depends on a browser tab.

Needs an API key in the environment (YT_API_KEY); runs in the youtube-api workflow (GitHub Actions can reach
googleapis.com; the build machine cannot). Quota: 10,000 units a day; a playlists/playlistItems/videos page costs 1 unit
(50 rows), a search 100 — so playlists and lectures are nearly free and searches are rationed.

    python3 pipeline/yt_api.py playlists work/yt_api/channels.json      channel ids -> work/yt_api/channel_playlists.json
                                                                         {chid: {"title", "uploads": "UU…", "playlists": [{id,title,n,desc}]}}
    python3 pipeline/yt_api.py pull work/yt_api/pids.json                playlist ids -> raw/institutional/pulled_api_<date>.json
                                                                         in the browser runner's shape ({pid: {title, desc, count, owner,
                                                                         ownerId, items: [{id,title,len,idx,ch,chid,info,pub}]}}), plus
                                                                         raw/youtube/meta_api_<date>.json (durations, views, descriptions,
                                                                         tags, category) so merge_pulled.py and the labelers work unchanged
    python3 pipeline/yt_api.py videos work/yt_api/vids.json              video ids -> raw/youtube/meta_api_<date>.json
"""
import datetime
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
KEY = os.environ.get("YT_API_KEY", "")
BASE = "https://www.googleapis.com/youtube/v3/"
UNITS = {"n": 0}


def call(endpoint, **params):
    params["key"] = KEY
    url = BASE + endpoint + "?" + urllib.parse.urlencode(params, doseq=True)
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=60) as r:
                UNITS["n"] += 100 if endpoint == "search" else 1
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code in (403, 429) and "quota" in body.lower():
                sys.exit(f"quota exhausted after {UNITS['n']} units: {body}")
            if e.code == 404:
                return None
            print("HTTP", e.code, endpoint, body, file=sys.stderr)
            if e.code < 500 and i >= 1:
                return None
        except Exception as e:                   # noqa: BLE001
            print("retry", endpoint, e, file=sys.stderr)
        time.sleep(2 * (i + 1))
    return None


def paged(endpoint, **params):
    token = None
    while True:
        d = call(endpoint, **params, **({"pageToken": token} if token else {}))
        if not d:
            return
        for it in d.get("items", []):
            yield it
        token = d.get("nextPageToken")
        if not token:
            return


def iso_seconds(s):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return None
    d, h, mi, se = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


def playlists(channels_path):
    chids = json.load(open(channels_path, encoding="utf-8"))
    chids = [c["id"] if isinstance(c, dict) else c for c in chids]
    out_path = P("work", "yt_api", "channel_playlists.json")
    os.makedirs(P("work", "yt_api"), exist_ok=True)
    out = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {}
    for i in range(0, len(chids), 50):
        batch = [c for c in chids[i:i + 50] if c not in out]
        if not batch:
            continue
        for ch in (call("channels", part="snippet,contentDetails,statistics", id=",".join(batch), maxResults=50) or {}).get("items", []):
            out[ch["id"]] = {"title": ch["snippet"]["title"], "subs": int(ch["statistics"].get("subscriberCount") or 0), "videos": int(ch["statistics"].get("videoCount") or 0),
                             "uploads": ch["contentDetails"]["relatedPlaylists"].get("uploads"), "playlists": []}
    for chid in chids:
        rec = out.get(chid)
        if rec is None or rec.get("done"):
            continue
        rec["playlists"] = [{"id": p["id"], "title": p["snippet"]["title"], "n": p["contentDetails"]["itemCount"], "desc": (p["snippet"].get("description") or "")[:300]}
                            for p in paged("playlists", part="snippet,contentDetails", channelId=chid, maxResults=50)]
        rec["done"] = True
        json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        print(f"{rec['title'][:50]:50} {len(rec['playlists']):4} playlists  ({UNITS['n']} units)", flush=True)
    print(f"{len(out)} channels -> {out_path}; {UNITS['n']} units")


def videos_meta(ids):
    meta = {}
    for i in range(0, len(ids), 50):
        d = call("videos", part="snippet,contentDetails,statistics", id=",".join(ids[i:i + 50]), maxResults=50)
        for v in (d or {}).get("items", []):
            sn, cd, st = v["snippet"], v["contentDetails"], v.get("statistics", {})
            meta[v["id"]] = {"title": sn["title"], "ch": sn["channelTitle"], "chid": sn["channelId"], "len": iso_seconds(cd.get("duration")),
                             "views": int(st["viewCount"]) if st.get("viewCount") else None, "pub": sn["publishedAt"][:10], "desc": (sn.get("description") or "")[:1500],
                             "kw": (sn.get("tags") or [])[:12], "cat": sn.get("categoryId"), "lang": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage"),
                             "caption": cd.get("caption") == "true", "live": sn.get("liveBroadcastContent")}
    return meta


def pull(pids_path):
    pids = json.load(open(pids_path, encoding="utf-8"))
    pids = [p["id"] if isinstance(p, dict) else p for p in pids]
    today = datetime.date.today().isoformat()
    out_path = P("raw", "institutional", f"pulled_api_{today}.json")
    out = json.load(open(out_path, encoding="utf-8")) if os.path.exists(out_path) else {"pulled": today, "courses": {}, "errors": {}}
    meta_path = P("raw", "youtube", f"meta_api_{today}.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}
    for pid in pids:
        if pid in out["courses"] or pid in out["errors"]:
            continue
        head = (call("playlists", part="snippet,contentDetails", id=pid) or {}).get("items") or []
        if not head:
            out["errors"][pid] = "not found or private"
            continue
        h = head[0]
        items = []
        for k, it in enumerate(paged("playlistItems", part="snippet,contentDetails", playlistId=pid, maxResults=50), 1):
            sn = it["snippet"]
            if sn["title"] in ("Private video", "Deleted video") or not sn.get("resourceId", {}).get("videoId"):
                continue
            items.append({"id": sn["resourceId"]["videoId"], "title": sn["title"], "idx": k, "ch": sn.get("videoOwnerChannelTitle") or "", "chid": sn.get("videoOwnerChannelId") or "",
                          "pub": (it.get("contentDetails", {}).get("videoPublishedAt") or sn.get("publishedAt") or "")[:10], "info": ""})
        new_ids = [it["id"] for it in items if it["id"] not in meta]
        meta.update(videos_meta(new_ids))
        for it in items:
            m = meta.get(it["id"]) or {}
            it["len"] = m.get("len")
            it["info"] = f"{m.get('views') or 0:,} views · {it['pub']}" if m else ""
            if m.get("live") == "upcoming" or (m.get("len") == 0):
                it["unavailable"] = True
        items = [it for it in items if it["id"] in meta]           # videos.list drops what is private, removed or region-blocked
        out["courses"][pid] = {"title": h["snippet"]["title"], "desc": h["snippet"].get("description") or "", "count": f"{h['contentDetails']['itemCount']} videos",
                               "owner": h["snippet"]["channelTitle"], "ownerId": h["snippet"]["channelId"], "n": len(items), "items": items, "via": "data-api"}
        json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False)
        json.dump(meta, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False)
        print(f"{pid} {len(items):4} items  {h['snippet']['title'][:60]}  ({UNITS['n']} units)", flush=True)
    print(f"{len(out['courses'])} playlists -> {out_path}; {len(meta)} videos -> {meta_path}; {UNITS['n']} units; errors: {len(out['errors'])}")


def videos_cmd(vids_path):
    ids = json.load(open(vids_path, encoding="utf-8"))
    today = datetime.date.today().isoformat()
    meta_path = P("raw", "youtube", f"meta_api_{today}.json")
    meta = json.load(open(meta_path, encoding="utf-8")) if os.path.exists(meta_path) else {}
    meta.update(videos_meta([v for v in ids if v not in meta]))
    json.dump(meta, open(meta_path, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"{len(meta)} videos -> {meta_path}; {UNITS['n']} units")


if __name__ == "__main__":
    if not KEY:
        sys.exit("YT_API_KEY is not set")
    if len(sys.argv) > 2 and sys.argv[1] == "playlists":
        playlists(sys.argv[2])
    elif len(sys.argv) > 2 and sys.argv[1] == "pull":
        pull(sys.argv[2])
    elif len(sys.argv) > 2 and sys.argv[1] == "videos":
        videos_cmd(sys.argv[2])
    else:
        sys.exit(__doc__)
