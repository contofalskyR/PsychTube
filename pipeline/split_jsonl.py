#!/usr/bin/env python3
"""Split a JSONL file into numbered parts for parallel labeling.

usage: split_jsonl.py <in.jsonl> <out_prefix> <rows_per_part>
writes <out_prefix>_00.jsonl, _01.jsonl, ... and prints the parts.
"""
import math
import sys

src, prefix, n = sys.argv[1], sys.argv[2], int(sys.argv[3])
rows = [l for l in open(src, encoding="utf-8") if l.strip()]
parts = math.ceil(len(rows) / n) if rows else 0
for i in range(parts):
    with open(f"{prefix}_{i:02d}.jsonl", "w", encoding="utf-8") as f:
        f.writelines(rows[i * n:(i + 1) * n])
print(f"{len(rows)} rows -> {parts} parts of {n} ({prefix}_00..{parts - 1:02d}.jsonl)")
