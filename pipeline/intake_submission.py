#!/usr/bin/env python3
"""Turn a "Submit a course" GitHub issue into a submission record the build understands.

    python3 pipeline/intake_submission.py 42            # reads issue #42 with the gh CLI
    python3 pipeline/intake_submission.py issue.md 42   # or a saved copy of the issue body

Writes raw/institutional/submissions/issue-<n>.json:

    {"issue": 42, "pid": "PL...", "url": "...", "course": "...", "inst": "...", "unit": "...", "lecturer": "...",
     "faculty_page": "...", "year": 2024, "level": "intro", "materials": [{"label": "Syllabus", "url": "..."}, ...],
     "notes": "...", "submitted_by": "lecturer" | "institution" | "other", "control_verified": false,
     "status": "pending"}

and prints what to do next. The lectures themselves still come in through the normal path (pull the playlist,
`merge_pulled.py`, label, build): the submission adds the materials, the "submitted by the lecturer" line and
the faculty page for the publisher check. `status` becomes "listed" once the playlist is in courses.json;
`control_verified` is for the day we ask lecturers to put a token in the playlist description.
"""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

FIELDS = {
    "Playlist URL": "url", "Course code and title": "course", "Institution": "inst", "Department or programme (optional)": "unit",
    "Lecturer(s)": "lecturer", "Faculty page URL": "faculty_page", "Term and year": "term", "Level": "level",
    "Syllabus URL (optional)": "syllabus", "Readings URL (optional)": "readings", "Other materials (optional)": "materials",
    "Anything else": "notes", "Who is submitting": "who",
}
LEVEL = {"Introductory": "intro", "Intermediate": "intermediate", "Advanced": "advanced", "Public lectures": "public"}
WHO = {"The lecturer": "lecturer", "The institution's media or teaching office": "institution"}


def parse_form(body):
    """GitHub renders an issue form as '### Label\\n\\nvalue' blocks; empty optional fields say '_No response_'."""
    out = {}
    for m in re.finditer(r"^### (.+?)\s*\n(.*?)(?=^### |\Z)", body, re.S | re.M):
        label, value = m.group(1).strip(), m.group(2).strip()
        key = FIELDS.get(label)
        if key and value and value != "_No response_":
            out[key] = value
    return out


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    if os.path.exists(args[0]):
        body = open(args[0], encoding="utf-8").read()
        n = int(args[1]) if len(args) > 1 else 0
    else:
        n = int(args[0])
        body = json.loads(subprocess.check_output(["gh", "issue", "view", str(n), "--json", "body"], text=True))["body"]
    f = parse_form(body)
    url = f.get("url", "")
    pid = (re.search(r"[?&]list=([A-Za-z0-9_-]+)", url) or [None, None])[1]
    materials = []
    if f.get("syllabus"):
        materials.append({"label": "Syllabus", "url": f["syllabus"].strip()})
    if f.get("readings"):
        materials.append({"label": "Readings", "url": f["readings"].strip()})
    for line in (f.get("materials") or "").splitlines():
        m = re.match(r"\s*(.+?)\s*[—–\-:]+\s*(https?://\S+)", line)
        if m:
            materials.append({"label": m.group(1).strip()[:40], "url": m.group(2)})
    year = (re.search(r"(19|20)\d{2}", f.get("term", "")) or [None])[0]
    rec = {
        "issue": n, "pid": pid, "url": url, "course": f.get("course", ""), "inst": f.get("inst", ""), "unit": f.get("unit") or None,
        "lecturer": f.get("lecturer", ""), "faculty_page": f.get("faculty_page", ""), "term": f.get("term") or None,
        "year": int(year) if year else None, "level": LEVEL.get(f.get("level", ""), None), "materials": materials,
        "notes": f.get("notes") or "", "submitted_by": WHO.get(f.get("who", ""), "other"), "control_verified": False, "status": "pending",
    }
    os.makedirs(P("raw", "institutional", "submissions"), exist_ok=True)
    out = P("raw", "institutional", "submissions", f"issue-{n}.json")
    json.dump(rec, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"wrote {out}")
    print(json.dumps(rec, ensure_ascii=False, indent=1))
    print("\nnext:")
    print(f" 1. check the faculty page names the lecturer: {rec['faculty_page']}")
    if pid:
        print(f" 2. pull the playlist ({pid}) with the runner (pipeline/NOTES.md) and merge it: python3 pipeline/merge_pulled.py <pull file>")
        print(f"    - inst for the merge: {rec['inst']!r}; if the playlist is on the lecturer's own channel add the channel to pipeline/publishers.json (verified: true with the faculty page as evidence)")
    else:
        print(" 2. no YouTube playlist id in the URL: add the course to raw/institutional/courses.json by hand (provider panopto/archive, see README)")
    print(" 3. python3 pipeline/make_inst_batches.py 150 --only-mixed, label, then set status to \"listed\" in the submission file and rebuild")


if __name__ == "__main__":
    main()
