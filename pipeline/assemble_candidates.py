#!/usr/bin/env python3
"""Turn the YouTube sweep into triage batches.

Reads  raw/sweep/channels.json   {chid: {title, subs, verified, psychCh, playlists:[{id,title,n,src}]}}  (institutional channels)
       raw/sweep/topic.json      [{id,title,ch,chid,verified,count,q:[...]}]                               (topic playlist searches)
       raw/institutional/courses.json (already-ingested playlists are skipped)
Writes work/triage/batch_NN.jsonl  -> label with pipeline/classify/INSTRUCTIONS_triage.md into work/triage/out_NN.jsonl

Usage: python3 pipeline/assemble_candidates.py [batch_size]
"""
import json
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
size = int(sys.argv[1]) if len(sys.argv) > 1 else 150

have = {c["pid"] for c in json.load(open(P("raw", "institutional", "courses.json")))["courses"]}
chans = json.load(open(P("raw", "sweep", "channels.json"))) if os.path.exists(P("raw", "sweep", "channels.json")) else {}
topic = json.load(open(P("raw", "sweep", "topic.json"))) if os.path.exists(P("raw", "sweep", "topic.json")) else []

EXAM = re.compile(r"UGC|NET\b|CUET|UPSC|\bCSS\b|\bPMS\b|MCAT|EPPP|NCLEX|NORCET|AIIMS|A[- ]?Level|GCSE|IGCSE|AP Psych|exam|preparation|MCQ|notes|revision|BLEPP|IGNOU|AIOU|nursing|crash course|short lectures?|Adda247|coaching|tutor|tuition|study material|competitive|Classes by|academy", re.I)
MIRROR = re.compile(r"Sapolsky|Peterson|Paul Bloom|Yale|Stanford|MIT\b|Harvard|Berkeley|Oxford|OpenCourseWare|CrashCourse|Khan", re.I)
YOUTUBER = re.compile(r"CrashCourse|khanacademy|Professor Dave|Psych2Go|Sprouts|Practical Psychology|Psych Explained|Cognito|Mr\. Sinn|Medicosis|Dirty Medicine|Osmosis|Ninja Nerd|Simple Psychology|TED", re.I)
PERSON = re.compile(r"^(Dr\.?|Prof\.?|Professor)?\s*[A-Z][a-z]+(\s[A-Z]\.)?\s[A-Z][a-zA-Z'\-]+(,?\s(PhD|MD|Ph\.D\.))?$")


def ascii_ratio(t):
    return sum(1 for ch in t if ord(ch) < 128) / max(1, len(t))


rows = []
seen = set()
for chid, c in chans.items():
    for pl in c.get("playlists", []):
        pid = pl["id"]
        if pid in have or pid in seen or (pl.get("n") is not None and pl["n"] < 3):
            continue
        seen.add(pid)
        rows.append({"pid": pid, "title": pl["title"], "channel": c["title"], "channel_verified": bool(c.get("verified")),
                     "count": pl.get("n"), "source": "sweep", "queries": [], "found_by": pl.get("src")})
for pl in topic:
    pid = pl["id"]
    if pid in have or pid in seen or (pl.get("count") is not None and pl["count"] < 3):
        continue
    ch = pl.get("ch") or ""
    title = pl.get("title") or ""
    if ascii_ratio(title + ch) < 0.85:
        continue
    if EXAM.search(ch) or EXAM.search(title) or YOUTUBER.search(ch):
        continue
    inst_like = re.search(r"universit|college|institute|school|department|dept\b|faculty|academy of|psychiatr|hospital|medicine|medical|centre|center|society|association|foundation|laborator|NPTEL|OCW|IIT", ch, re.I)
    if not inst_like and MIRROR.search(title):      # a non-institutional channel posting a famous course = a mirror
        continue
    if not inst_like and not PERSON.match(ch.strip()) and not re.search(r"lecture|course|PSY|seminar|colloquium|rounds", title, re.I):
        continue
    seen.add(pid)
    rows.append({"pid": pid, "title": title, "channel": ch, "channel_verified": bool(pl.get("verified")), "count": pl.get("count"),
                 "source": "search", "queries": pl.get("q", [])[:3]})

os.makedirs(P("work", "triage"), exist_ok=True)
for f in os.listdir(P("work", "triage")):
    if f.startswith("batch_"):
        os.remove(P("work", "triage", f))
n = math.ceil(len(rows) / size) if rows else 0
for i in range(n):
    with open(P("work", "triage", f"batch_{i:02d}.jsonl"), "w", encoding="utf-8") as f:
        for r in rows[i * size:(i + 1) * size]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"{len(rows)} candidate playlists ({sum(1 for r in rows if r['source']=='sweep')} from channel sweep, {sum(1 for r in rows if r['source']=='search')} from topic searches) -> {n} batches in work/triage/")
