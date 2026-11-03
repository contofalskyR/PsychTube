#!/usr/bin/env python3
"""Merge round-5 sweep results (channel playlists + topic playlist searches) into raw/sweep/.

    python3 pipeline/merge_r5_sweep.py <transfer.json>

<transfer.json> is {"pl": {chid: {title, pl: [{id,title,n}] | {error}}}, "q": {query: [{id,title,ch,chid,verified,count}] | {error}},
"meta": {chid: {subs, verified}}} as dumped from the browser pane (gzip+base64 handled by the caller).

Channels flagged GENERAL carry everything a university posts; only playlists whose title reads psychology/cognition/
neuroscience/language/mind/decision are kept from them. Dedicated channels keep every playlist (triage decides).
Channels without a playlists tab get their uploads playlist (UU + id) as one candidate when the caller has looked at the uploads.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

GENERAL = {"MIT OpenCourseWare", "Harvard University", "Nobel Prize", "The Royal Society", "Royal Society of Arts", "University of Nottingham",
           "University of Amsterdam", "Harvard Graduate School of Education", "National Academy of Sciences", "Scripps Research",
           "Beckman Institute at Illinois", "The University of Chicago Booth School of Business", "The Rockefeller University",
           "Nottingham Trent University", "Tata Institute of Fundamental Research", "University of Waterloo Faculty of Arts",
           "Social and Behavioural Sciences Leiden University", "Columbia University's Zuckerman Institute"}
RELEVANT = re.compile(r"psych|cognit|cogsci|neuro|brain|mind\b|minds\b|mental|memory|perception|attention|conscious|language|linguist|"
                      r"speech|reading|dyslexia|autism|infan|child|development|adolescen|learning|emotion|decision|behavio|judg|"
                      r"reason|intelligen|moral|social|personality|happiness|sleep|dream|addict|schizo|depress|anxiety|"
                      r"economic sciences|physiology or medicine|9\.\d|24\.9|philosoph|education|teaching and learning|"
                      r"sackler|colloqui|lecture|seminar|symposi|keynote|distinguished|prize lecture|nobel lecture", re.I)
NOISE = re.compile(r"\b(shorts|trailer|promo|campus tour|admissions|commencement|graduation|orientation|football|basketball|"
                   r"fundrais|giving day|alumni weekend|open day|student life|housing|dining)\b", re.I)


def main():
    src = json.load(open(sys.argv[1], encoding="utf-8"))
    chans_path, topic_path = P("raw", "sweep", "channels.json"), P("raw", "sweep", "topic.json")
    chans = json.load(open(chans_path, encoding="utf-8"))
    topic = json.load(open(topic_path, encoding="utf-8"))
    meta = src.get("meta", {})
    added_ch = added_pl = 0
    for chid, c in src["pl"].items():
        title = c["title"]
        pls = c["pl"]
        rows = []
        if isinstance(pls, list):
            for p in pls:
                if not p.get("title") or NOISE.search(p["title"]):
                    continue
                if title in GENERAL and not RELEVANT.search(p["title"]):
                    continue
                rows.append({"id": p["id"], "title": p["title"], "n": p.get("n"), "src": "enum"})
        up = c.get("uploads")                                      # {"n": count, "sample": [...]} when the caller looked at the uploads
        if up and up.get("keep"):
            rows.append({"id": "UU" + chid[2:], "title": f"{title} — all uploads", "n": up.get("n"), "src": "uploads"})
        if chid in chans:
            have = {p["id"] for p in chans[chid].get("playlists", [])}
            new = [r for r in rows if r["id"] not in have]
            chans[chid].setdefault("playlists", []).extend(new)
            added_pl += len(new)
        else:
            m = meta.get(chid, {})
            chans[chid] = {"id": chid, "title": title, "subs": m.get("subs"), "verified": bool(m.get("verified")), "psychCh": title not in GENERAL,
                           "round": 5, "playlists": rows}
            added_ch += 1
            added_pl += len(rows)
    by_pid = {p["id"]: p for p in topic}
    added_t = 0
    for q, res in src["q"].items():
        if not isinstance(res, list):
            continue
        for p in res:
            if not p.get("id"):
                continue
            if p["id"] in by_pid:
                qs = by_pid[p["id"]].setdefault("q", [])
                if q not in qs:
                    qs.append(q)
            else:
                row = {"id": p["id"], "title": p.get("title"), "ch": p.get("ch"), "chid": p.get("chid"), "verified": bool(p.get("verified")),
                       "count": p.get("count"), "q": [q], "round": 5}
                topic.append(row)
                by_pid[p["id"]] = row
                added_t += 1
    json.dump(chans, open(chans_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(topic, open(topic_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"channels: +{added_ch} (now {len(chans)}), channel playlists: +{added_pl}; topic playlists: +{added_t} (now {len(topic)})")


if __name__ == "__main__":
    main()
