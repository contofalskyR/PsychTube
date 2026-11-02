#!/usr/bin/env python3
"""Pull YouTube-linking comments and posts from psychology subreddits via the Arctic Shift API.

Usage:  python3 pipeline/reddit_crawler.py [subreddit ...]
Writes: raw/reddit/reddit_<timestamp>.json  {"records": [...comments...], "posts": [...]}
Resumes from raw/reddit/progress.json if interrupted.

Needs an open network (arctic-shift.photon-reddit.com). The archive rate-limits hard: expect
"Timeout. Maybe slow down a bit" (422) and 429s; the script backs off and keeps going. Full
comment scans are slow (~100–1000 comments per request); the posts keyword search is quick.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "raw", "reddit")
os.makedirs(OUT, exist_ok=True)
API = "https://arctic-shift.photon-reddit.com/api"
UA = "PsychTube crawler (personal project; be gentle)"

DEFAULT_SUBS = ["BehavioralEconomics", "cogsci", "psychologyresearch", "socialpsychology", "cognitiveScience", "neurophilosophy",
                "AcademicPsychology", "neuroscience", "IOPsychology", "ClinicalPsychology", "neuro", "askpsychology",
                "psychoanalysis", "PsychologyStudents", "Psychiatry", "psychology"]

YT = re.compile(r"(?:youtube\.com/watch\?(?:[^\s)\]]*?&)?v=|youtube\.com/(?:embed|shorts|live|v)/|youtu\.be/)([A-Za-z0-9_-]{11})")
TS = re.compile(r"^[^\s)\]]*?[?&#](?:t|start)=(\d+(?:[hms]\d*)*)")


def extract(text):
    out, seen = [], set()
    for m in YT.finditer(text or ""):
        vid = m.group(1)
        if vid in seen:
            continue
        seen.add(vid)
        t = TS.match(text[m.end():m.end() + 120])
        out.append({"id": vid, "t": t.group(1)} if t else {"id": vid})
    return out


def trim(body, n):
    body = body or ""
    if len(body) <= n:
        return body
    i = max(0, body.lower().find("youtu"))
    s = max(0, min(i - n // 2, len(body) - n))
    return ("…" if s else "") + body[s:s + n] + ("…" if s + n < len(body) else "")


def get(url, tries=12):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.load(r)
            if d.get("data") is not None:
                return d["data"]
            err = d.get("error", "")
        except urllib.error.HTTPError as e:
            err = f"{e.code}"
            if e.code == 429:
                time.sleep(25)
                continue
        except Exception as e:  # network blip
            err = str(e)
        print("  retry:", err[:60], file=sys.stderr)
        time.sleep(8 + 4 * k)
    return None


progress_path = os.path.join(OUT, "progress.json")
progress = json.load(open(progress_path)) if os.path.exists(progress_path) else {}
records, posts, seen = [], [], set()


def save():
    json.dump(progress, open(progress_path, "w"))


def posts_kw(sub):
    key = f"{sub}|posts"
    if progress.get(key) == "done":
        return
    cursor, now, win = progress.get(key) or 1230768000, int(time.time()), 86400 * 365 * 4
    while cursor < now:
        before = min(cursor + win, now + 1)
        q = urllib.parse.urlencode({"subreddit": sub, "query": "youtube", "limit": 100, "sort": "asc", "after": cursor, "before": before,
                                    "fields": "id,author,title,url,selftext,created_utc,score,num_comments,subreddit"})
        data = get(f"{API}/posts/search?{q}")
        if data is None:
            win = max(86400 * 30, win // 2)
            continue
        for it in data:
            if ("p", it["id"]) in seen:
                continue
            seen.add(("p", it["id"]))
            v = extract((it.get("url") or "") + " " + (it.get("selftext") or ""))
            if v:
                posts.append({"s": it.get("subreddit", sub), "id": it["id"], "a": it.get("author"), "t": it["created_utc"], "sc": it.get("score"),
                              "nc": it.get("num_comments"), "ti": it.get("title"), "u": it.get("url"), "st": trim(it.get("selftext"), 500), "v": v})
        if len(data) >= 100:
            cursor = max(cursor + 1, data[-1]["created_utc"])
        else:
            cursor, win = before, min(86400 * 365 * 8, int(win * 1.5))
        progress[key] = cursor
        time.sleep(1.5)
    progress[key] = "done"
    save()
    print(f"r/{sub}: posts done, {len(posts)} link posts so far")


def comments_scan(sub):
    key = f"{sub}|comments"
    if progress.get(key) == "done":
        return
    cursor, now, pages = progress.get(key) or 1230768000, int(time.time()), 0
    while cursor < now:
        q = urllib.parse.urlencode({"subreddit": sub, "limit": "auto", "sort": "asc", "after": cursor,
                                    "fields": "id,author,body,created_utc,link_id,parent_id,score,subreddit"})
        data = get(f"{API}/comments/search?{q}")
        if data is None:
            continue
        if not data:
            break
        for it in data:
            if ("c", it["id"]) in seen:
                continue
            seen.add(("c", it["id"]))
            v = extract(it.get("body"))
            if v:
                records.append({"s": it.get("subreddit", sub), "c": it["id"], "a": it.get("author"), "t": it["created_utc"], "sc": it.get("score"),
                                "l": it.get("link_id"), "p": it.get("parent_id"), "b": trim(it.get("body"), 700), "v": v})
        cursor = max(cursor + 1, data[-1]["created_utc"])
        progress[key] = cursor
        pages += 1
        if pages % 20 == 0:
            save()
            print(f"  r/{sub} {time.strftime('%Y-%m-%d', time.gmtime(cursor))} {len(records)} link comments", file=sys.stderr)
        time.sleep(0.7)
    progress[key] = "done"
    save()
    print(f"r/{sub}: comments done, {len(records)} link comments so far")


subs = sys.argv[1:] or DEFAULT_SUBS
try:
    for s in subs:
        posts_kw(s)
    for s in subs:
        comments_scan(s)
finally:
    path = os.path.join(OUT, f"reddit_{int(time.time())}.json")
    json.dump({"records": records, "posts": posts, "source": "arctic-shift", "subs": subs}, open(path, "w"))
    save()
    print(f"wrote {path}: {len(records)} comments, {len(posts)} posts")
