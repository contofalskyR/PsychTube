#!/usr/bin/env python3
"""UC Berkeley webcasts on the Internet Archive -> courses.json records.

    python3 pipeline/archive_courses.py            (reads work/archive/items_ucberkeley-webcast.json and work/archive/files.json,
                                                    both from the archive workflow's archive-data branch)

Two kinds of item in the collection:
- one item per lecture (2011–2015), `ucberkeley_webcast_<original YouTube id>`, a single MP4 — the form the first 22 courses used;
- one item per course (the iTunes U feeds, 2006–2014), `ucberkeley_webcast_itunesu_<n>`, with every lecture as a file; most of
  the pre-2010 ones are audio-only (no video file) and are left out here.
A course item becomes one course whose lectures are its MP4 files, each lecture id `<item>_<track>` with `item` carrying the
archive identifier the player needs. Course-terms already in courses.json (from per-lecture items) are not added again, and a
dated stray lecture item ("Psychology 160 - 2014-09-08: Research Methods") joins its existing course when that lecture is missing.
"""
import datetime
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
DEPT = {"PSYCH": "Psychology", "COG SCI": "Cognitive Science", "PHILOS": "Philosophy", "ECON": "Economics", "MCB": "Molecular and Cell Biology"}
OWNER = "UC Berkeley (webcast.berkeley, Internet Archive)"
TERM_WORD = {"Sp": "Spring", "Fa": "Fall", "Su": "Summer"}


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def term_of(date):
    y, m = int(date[:4]), int(date[5:7])
    return ("Spring" if m <= 5 else "Summer" if m <= 7 else "Fall") + f" {y}"


def course_name(item, meta):
    """'PSYCH 164 LEC 001 Sp10\\n\\nSocial Cognition' -> ('Psychology 164: Social Cognition', 'Spring 2010')."""
    desc = (meta.get("description") or item.get("description") or "")
    m = re.match(r"\s*([A-Z &]+?)\s+(C?\d+[A-Z]*)\s+LEC\s+\d+\s+(Sp|Fa|Su)(\d{2})\s*\n+\s*(.+)", desc)
    if m:
        dept, num, t, yy, title = m.groups()
        return f"{DEPT.get(dept.strip(), dept.strip().title())} {num}: {title.strip()}", f"{TERM_WORD[t]} 20{yy}"
    t = item.get("title") or ""
    m = re.match(r"\s*([A-Za-z ]+?)\s*(C?\d+[A-Z]*),?\s*(?:\d{3})?\s*-\s*(Spring|Fall|Summer)\s+(\d{4})", t)
    if m:
        dept, num, term, year = m.groups()
        return f"{DEPT.get(dept.strip().upper(), dept.strip().title())} {num}", f"{term} {year}"
    return None, None


KNOWN_TITLES = {"Psychology 160": "Social Psychology", "Psychology 1": "General Psychology", "Philosophy 3": "The Nature of Mind"}


def main():
    items = {it["identifier"]: it for it in json.load(open(P("work", "archive", "items_ucberkeley-webcast.json"), encoding="utf-8"))}
    files = json.load(open(P("work", "archive", "files.json"), encoding="utf-8"))
    cj = json.load(open(P("raw", "institutional", "courses.json"), encoding="utf-8"))
    existing = {c["pid"]: c for c in cj["courses"] if c.get("provider") == "archive"}
    have_terms = {}
    for pid, c in existing.items():
        m = re.match(r"(.+?):.*\((Spring|Fall|Summer) (\d{4})\)", c["title"])
        if m:
            have_terms[(m.group(1).strip(), f"{m.group(2)} {m.group(3)}")] = pid
    today = datetime.date.today().isoformat()
    added, joined = [], []
    for ident, meta in files.items():
        item = items.get(ident, {"identifier": ident, "title": meta.get("title") or ""})
        vids = [v for v in (meta.get("videos") or []) if v["name"].lower().endswith(".mp4")]
        if not vids:
            continue
        if len(vids) >= 5:                                     # a course item
            name, term = course_name(item, meta)
            if not name:
                print("no course name for", ident, item.get("title")); continue
            if ":" not in name and name in KNOWN_TITLES:
                name = f"{name}: {KNOWN_TITLES[name]}"
            key = (name.split(":")[0].strip(), term)
            if key in have_terms:
                continue                                       # the same course-term is already in from the per-lecture items
            def track(v):
                m = re.match(r"\s*(\d+)\.", v["name"]) or re.search(r"Lecture\s+(\d+)", v.get("title") or v["name"])
                return int(v["track"]) if str(v.get("track") or "").isdigit() else (int(m.group(1)) if m else 999)
            vids.sort(key=track)
            rows = []
            for k, v in enumerate(vids, 1):
                title = (v.get("title") or re.sub(r"^\d+\.\s*", "", v["name"]).rsplit(".", 1)[0]).strip()
                dm = re.search(r"(20\d{2}-\d{2}-\d{2})", v["name"])          # "03. 2010-01-27 - Lecture 3.mp4": the lecture's own date
                rows.append({"id": f"{ident}_{k}", "item": ident, "title": title, "len": int(v["length"]) if v.get("length") else None, "idx": k,
                             "ch": OWNER, "chid": None, "info": "", "pub": dm.group(1) if dm else ((item.get("date") or meta.get("date") or "")[:10] or None), "file": v["name"]})
            pid = "archive:" + slug(f"{name.split(':')[0]} {term}")
            if pid in existing:
                continue
            desc = re.sub(r"\s+", " ", (meta.get("description") or "")).strip()
            cj["courses"].append({
                "pid": pid, "provider": "archive", "host": "archive.org", "title": f"{name} ({term})", "owner": OWNER, "ownerId": None,
                "count": f"{len(rows)} videos", "desc": f"UC Berkeley's {name}, {term}, recorded by webcast.berkeley and published through iTunes U; "
                        f"Berkeley removed its lecture archive from YouTube in 2017 and these copies are preserved on the Internet Archive. {desc}".strip(),
                "inst": "UC Berkeley", "kind": "course", "n": len(rows), "items": rows, "url": f"https://archive.org/details/{ident}", "pulled": today,
                "triage": {"confidence": 0.9, "why": "webcast.berkeley course recording preserved on the Internet Archive"},
            })
            existing[pid] = cj["courses"][-1]
            have_terms[key] = pid
            added.append((pid, len(rows)))
        else:                                                  # a stray lecture item: join its course when the date says which
            t = item.get("title") or ""
            m = re.match(r"\s*([A-Za-z ]+?)\s*(C?\d+[A-Z]*)(?:,\s*\d{3})?\s*-\s*(\d{4}-\d{2}-\d{2})", t)
            if not m:
                continue
            dept, num, date = m.groups()
            course = f"{DEPT.get(dept.strip().upper(), dept.strip().title())} {num}"
            pid = have_terms.get((course, term_of(date)))
            if not pid:
                continue
            c = existing[pid]
            if any(it["id"] == ident for it in c["items"]):
                continue
            v = vids[0]
            c["items"].append({"id": ident, "title": re.sub(r"\s*\|.*$", "", t).strip(), "len": int(v["length"]) if v.get("length") else None, "idx": len(c["items"]) + 1,
                               "ch": OWNER, "chid": None, "info": "", "pub": date, "file": v["name"]})
            c["items"].sort(key=lambda it: (it.get("pub") or "9999", it["idx"]))
            for k, it in enumerate(c["items"], 1):
                it["idx"] = k
            c["n"] = len(c["items"]); c["count"] = f"{c['n']} videos"
            joined.append((pid, ident))
    json.dump(cj, open(P("raw", "institutional", "courses.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"added {len(added)} courses ({sum(n for _, n in added)} lectures):")
    for pid, n in added:
        print(f"  {pid} {n}")
    print(f"joined {len(joined)} stray lectures to existing courses: {[p for p, _ in joined]}")


if __name__ == "__main__":
    main()
