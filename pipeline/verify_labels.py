#!/usr/bin/env python3
"""Check per-lecture label files against their inputs: line counts, vid order, shape, topic ids.

usage: verify_labels.py [first_batch_index]   (default 0)
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)
first = int(sys.argv[1]) if len(sys.argv) > 1 else 0
tax = open(P("pipeline", "classify", "TAXONOMY.md"), encoding="utf-8").read()
topic_ids = set(re.findall(r"^- `([a-z0-9-]+)`", tax, re.M))
contested_ids = {c["id"] for c in json.load(open(P("pipeline", "taxonomy.json")))["contested_findings"]}
cw_ids = set(json.load(open(P("pipeline", "taxonomy.json")))["content_warnings"]) if isinstance(json.load(open(P("pipeline", "taxonomy.json")))["content_warnings"], list) else set()
bad = 0
for bf in sorted(glob.glob(P("work", "inst", "batch_*.jsonl"))):
    i = int(re.search(r"batch_(\d+)", bf).group(1))
    if i < first:
        continue
    of = bf.replace("batch_", "out_")
    if not os.path.exists(of):
        print(f"batch_{i:02d}: no output yet"); continue
    b = [json.loads(l) for l in open(bf, encoding="utf-8") if l.strip()]
    o = [json.loads(l) for l in open(of, encoding="utf-8") if l.strip()]
    probs = []
    if len(b) != len(o):
        probs.append(f"{len(o)} lines for {len(b)} rows")
    for x, y in zip(b, o):
        if x["vid"] != y.get("vid"):
            probs.append(f"vid order breaks at {x['vid']} vs {y.get('vid')}"); break
    for y in o:
        if not isinstance(y.get("keep"), bool):
            probs.append(f"{y.get('vid')}: keep not bool"); break
        if y.get("keep") and not (1 <= len(y.get("topics") or []) <= 3):
            probs.append(f"{y.get('vid')}: {len(y.get('topics') or [])} topics"); break
        for t in y.get("topics") or []:
            if t not in topic_ids:
                probs.append(f"{y.get('vid')}: unknown topic {t}"); break
        if y.get("contested") and y["contested"] not in contested_ids:
            probs.append(f"{y.get('vid')}: unknown contested {y['contested']}")
    kept = sum(1 for y in o if y.get("keep"))
    conf = sorted(set(round(y.get("confidence") or 0, 2) for y in o))
    print(f"batch_{i:02d}: {kept}/{len(o)} kept" + (f"  PROBLEMS: {'; '.join(probs[:3])}" if probs else "") + (f"  (only {len(conf)} distinct confidence values)" if len(conf) <= 1 else ""))
    bad += bool(probs)
print("files with problems:", bad)
