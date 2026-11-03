#!/usr/bin/env python3
"""Regenerate pipeline/classify/TAXONOMY.md from pipeline/taxonomy.json.

The labelers are told to use ids "from TAXONOMY.md", so the file must list every topic, content warning and
contested finding the build knows. It was once hand-written and fell behind (30 of 66 findings); now it is
generated, and the build's `CONTESTED` set is exactly what the labelers can see.

Usage: python3 pipeline/make_taxonomy_md.py
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
t = json.load(open(P("pipeline", "taxonomy.json"), encoding="utf-8"))
out = ["# PsychTube topics (use the ids)", ""]
for a in t["areas"]:
    out.append(f"## {a['name']} (area id: {a['id']})")
    for tp in a["topics"]:
        out.append(f"- `{tp['id']}` — {tp['name']}: {tp['description']}")
    out.append("")
out.append("# Content warnings (ids)")
out.append(", ".join(f"`{c}`" for c in t["content_warnings"]))
out.append("")
out.append("# Contested findings (ids) — tag a video only if it presents the finding as established fact, or if it critiques it")
out.append("")
out.append("Each id carries the status PsychTube shows. Findings that **held up** are listed too (Stroop, McGurk, rubber hand,")
out.append("inattentional blindness, split-brain, Asch, Robbers Cave, Pavlov…): tag a video that presents one of them as well,")
out.append("so it gets the reassuring chip. `contested_role` is `promotes` when the video presents the finding, `critique` when it")
out.append("pushes back on it (a lecture that teaches a classic while explaining its problems counts as `critique`).")
out.append("")
labels = t.get("status_labels", {})
for c in t["contested_findings"]:
    out.append(f"- `{c['id']}` — {c['name']} [{labels.get(c.get('status'), c.get('status', ''))}]: {c['note']}")
out.append("")
open(P("pipeline", "classify", "TAXONOMY.md"), "w", encoding="utf-8").write("\n".join(out))
print(f"TAXONOMY.md: {sum(len(a['topics']) for a in t['areas'])} topics, {len(t['content_warnings'])} content warnings, {len(t['contested_findings'])} contested findings")
