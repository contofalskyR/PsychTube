#!/usr/bin/env python3
"""Official lecture transcripts: which of our lectures have one, published by the course's own provider.

YouTube's captions are not fetched: there is no sanctioned route to other channels' caption tracks (the Data API only
serves a channel's own, the web endpoint refuses programmatic calls, and scraping them is bot access under YouTube's
terms). Two providers in the catalog publish transcripts themselves, under open licences, and those are linked:

- MIT OpenCourseWare: one PDF per lecture video at  https://ocw.mit.edu/courses/<course-slug>/<YouTubeId>_transcript.pdf
  (CC BY-NC-SA). The course slug is derived from the OCW playlist title ("MIT 9.13 The Human Brain, Spring 2019" ->
  9-13-the-human-brain-spring-2019); the PDF's existence is checked per lecture.
- Open Yale Courses: a transcript tab on every lecture page, https://oyc.yale.edu/<dept>/<course>/lecture-N (CC BY-NC-SA).
  The lecture number comes from the video title ("2. Foundations: This Is Your Brain" -> lecture-2).

Two steps, because the build machine cannot reach either site:

    python3 pipeline/transcripts.py plan     -> work/transcripts/plan.json: every candidate URL to check (HEAD)
    python3 pipeline/transcripts.py apply work/transcripts/checked.json
                                             -> pipeline/transcripts.json from {url: http_status} (200/30x = present)

build_catalog.py then sets series.tr {p, name, base, n} and video.tr (1 = derive from base + id; else a path under base).
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

OYC = {   # playlist -> OYC course path; the catalog's Yale playlists that are OYC courses (not the Everyday Parenting / Experts in Emotion series)
    "PL6A08EB4EEFF3E91F": ("psychology/psyc-110", "PSYC 110 Introduction to Psychology"),
    "PLh9mgdi4rNeyz0eiyC7pXr_20zPMi-tI9": ("psychology/psyc-123", "PSYC 123 The Psychology, Biology and Politics of Food"),
    "PL3F6BC200B2930084": ("philosophy/phil-181", "PHIL 181 Philosophy and the Science of Human Nature"),
}
TERM = {"fall": "fall", "spring": "spring", "summer": "summer", "iap": "january-iap"}


def ocw_slug(title):
    """'MIT 9.00SC Introduction to Psychology, Fall 2011' -> '9-00sc-introduction-to-psychology-fall-2011'."""
    m = re.match(r"MIT\s+((?:RES\.)?[\dA-Z]+\.[\dA-Z-]+J?)\s+(.*?),\s*(Fall|Spring|Summer|IAP)\s+(\d{2,4})\s*$", title.strip(), re.I)
    if not m:
        return None
    num, name, term, year = m.groups()
    year = int(year)
    if year < 100:
        year += 2000
    num = num.lower().replace(".", "-")
    name = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{num}-{name}-{TERM[term.lower()]}-{year}"


def plan():
    courses = json.load(open(P("raw", "institutional", "courses.json"), encoding="utf-8"))["courses"]
    out = []
    for c in courses:
        pid = c["pid"]
        if c.get("owner") == "MIT OpenCourseWare":
            slug = ocw_slug(c["title"])
            if not slug:
                print("no slug for", c["title"]); continue
            base = f"https://ocw.mit.edu/courses/{slug}/"
            for it in c["items"]:
                out.append({"pid": pid, "p": "ocw", "name": "MIT OpenCourseWare", "base": base, "vid": it["id"], "tr": 1, "url": f"{base}{it['id']}_transcript.pdf"})
        elif pid in OYC:
            path, name = OYC[pid]
            base = f"https://oyc.yale.edu/{path}/"
            for it in c["items"]:
                m = re.match(r"\s*(\d{1,2})\s*[.|]", it["title"]) or re.search(r"\b(\d{1,2})\s*$", it["title"])
                if not m:
                    continue
                n = int(m.group(1))
                out.append({"pid": pid, "p": "oyc", "name": "Open Yale Courses", "base": base, "vid": it["id"], "tr": f"lecture-{n}", "url": f"{base}lecture-{n}"})
    os.makedirs(P("work", "transcripts"), exist_ok=True)
    json.dump(out, open(P("work", "transcripts", "plan.json"), "w", encoding="utf-8"), indent=0)
    print(f"{len(out)} candidate transcript URLs for {len({o['pid'] for o in out})} courses -> work/transcripts/plan.json")


def apply(checked_path):
    """checked.json from fetch_transcripts.py: {video_id: {pid, p, src, status, words, pdf?, page?}}. The link the site shows is the
    provider's human-readable copy: the OCW transcript PDF (its path carries a hash, so it is stored, not derived) or the OYC page."""
    checked = json.load(open(checked_path, encoding="utf-8"))
    plan_rows = {r["vid"]: r for r in json.load(open(P("work", "transcripts", "plan.json"), encoding="utf-8"))}
    out = {}
    for vid, c in checked.items():
        r = plan_rows.get(vid)
        if not r or not (200 <= int(c.get("status") or 0) < 400):
            continue
        link = c.get("pdf") or c.get("src") or r["url"]
        if not link.startswith(r["base"]):
            continue
        rel = link[len(r["base"]):]
        e = out.setdefault(r["pid"], {"p": r["p"], "name": r["name"], "base": r["base"], "have": {}})
        e["have"][vid] = 1 if rel == f"{vid}_transcript.pdf" else rel
    json.dump(out, open(P("pipeline", "transcripts.json"), "w", encoding="utf-8"), indent=1)
    print(f"{sum(len(e['have']) for e in out.values())} transcripts in {len(out)} courses -> pipeline/transcripts.json")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "plan":
        plan()
    elif len(sys.argv) > 2 and sys.argv[1] == "apply":
        apply(sys.argv[2])
    else:
        sys.exit(__doc__)
