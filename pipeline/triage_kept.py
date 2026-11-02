#!/usr/bin/env python3
"""List the playlists the triage kept that still have to be pulled.

Reads work/triage/out_*.jsonl, pipeline/triage_overrides.json and raw/institutional/courses.json;
prints a JSON array of playlist ids (what pipeline/yt_pull_runner.js takes), or a summary with --summary.
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

ov = json.load(open(P("pipeline", "triage_overrides.json"))) if os.path.exists(P("pipeline", "triage_overrides.json")) else {}
drop_inst, drop_pid = set(ov.get("drop_inst", [])), set(ov.get("drop_pid", []))
have = {c["pid"] for c in json.load(open(P("raw", "institutional", "courses.json")))["courses"]}
rows = []
for f in sorted(glob.glob(P("work", "triage", "out_*.jsonl"))):
    for line in open(f, encoding="utf-8"):
        if line.strip():
            rows.append(json.loads(line))
kept = [r for r in rows if r.get("keep") and r["pid"] not in have and r["pid"] not in drop_pid and r.get("inst") not in drop_inst]
if "--summary" in sys.argv:
    print(f"{len(rows)} judged, {sum(1 for r in rows if r.get('keep'))} kept, {len(kept)} still to pull, {len({r.get('inst') for r in kept})} institutions")
else:
    print(json.dumps([r["pid"] for r in kept]))
