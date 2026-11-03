#!/usr/bin/env python3
"""Turn the YouTube sweep into triage batches.

Reads  raw/sweep/channels.json   {chid: {title, subs, verified, psychCh, playlists:[{id,title,n,src}]}}  (institutional channels)
       raw/sweep/topic.json      [{id,title,ch,chid,verified,count,q:[...]}]                               (topic playlist searches)
       raw/institutional/courses.json (already-ingested playlists are skipped)
       work/triage/out_*.jsonl        (already-judged playlists are skipped; new batches are numbered after them)
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
import glob
judged = set()                                           # already triaged (kept or dropped) in an earlier round
for f in glob.glob(P("work", "triage", "out_*.jsonl")):
    for line in open(f, encoding="utf-8"):
        if line.strip():
            judged.add(json.loads(line)["pid"])
have |= judged
chans = json.load(open(P("raw", "sweep", "channels.json"))) if os.path.exists(P("raw", "sweep", "channels.json")) else {}
topic = json.load(open(P("raw", "sweep", "topic.json"))) if os.path.exists(P("raw", "sweep", "topic.json")) else []

EXAM = re.compile(r"\bUGC\b|\bNET\b|\bCUET\b|\bUPSC\b|\bCSS\b|\bPMS\b|\bMCAT\b|\bEPPP\b|\bNCLEX\b|\bNORCET\b|\bAIIMS\b|\bA[- ]?Levels?\b|\bGCSE\b|\bIGCSE\b|\bAP Psych|\bexams?\b|\bpreparation\b|\bMCQs?\b|\bnotes\b|\brevision\b|\bBLEPP\b|\bIGNOU\b|\bAIOU\b|\bnursing\b|\bcrash course\b|\bshort lectures?\b|\bAdda247\b|\bcoaching\b|\btutors?\b|\btuition\b|\bstudy material\b|\bcompetitive\b|\bClasses by\b|\bacademy\b", re.I)   # word-anchored: "Examples" and "tutorials" are not exam prep
MIRROR = re.compile(r"Sapolsky|Peterson|Paul Bloom|Yale|Stanford|MIT\b|Harvard|Berkeley|Oxford|OpenCourseWare|CrashCourse|Khan", re.I)
YOUTUBER = re.compile(r"CrashCourse|khanacademy|Professor Dave|Psych2Go|\bSprouts\b|Practical Psychology|Psych Explained|\bCognito\b|Mr\. Sinn|Medicosis|Dirty Medicine|\bOsmosis\b|Ninja Nerd|Simple Psychology|\bTEDx?\b|\bTED-Ed\b", re.I)   # \bTED\b: not "animated" or "Associated"
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
done_idx = [int(m.group(1)) for f in glob.glob(P("work", "triage", "out_*.jsonl")) for m in [re.search(r"out_(\d+)\.jsonl$", f)] if m]
first = max(done_idx) + 1 if done_idx else 0             # new batches are numbered after the answered ones
for f in os.listdir(P("work", "triage")):
    m = re.match(r"batch_(\d+)\.jsonl$", f)
    if m and int(m.group(1)) not in done_idx:            # unanswered inputs from an earlier run
        os.remove(P("work", "triage", f))
n = math.ceil(len(rows) / size) if rows else 0
for i in range(n):
    with open(P("work", "triage", f"batch_{first + i:02d}.jsonl"), "w", encoding="utf-8") as f:
        for r in rows[i * size:(i + 1) * size]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"{len(rows)} candidate playlists ({sum(1 for r in rows if r['source']=='sweep')} from channel sweep, {sum(1 for r in rows if r['source']=='search')} from topic searches) -> {n} batches in work/triage/ (batch_{first:02d}.jsonl…)")
