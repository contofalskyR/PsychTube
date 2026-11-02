#!/usr/bin/env python3
"""Assemble base64 chunks saved as browser tool results into one gunzipped file.

usage: assemble_chunks.py <out-file> <chunk-file-1> <chunk-file-2> ...
Chunks are ordered by their embedded "part" suffix (e.g. videos-0, videos-1) if present,
otherwise by the order given.
"""
import base64
import gzip
import json
import re
import sys


def load(path):
    raw = json.load(open(path))
    text = raw[0]["text"] if isinstance(raw, list) else raw["text"]
    cut = text.rfind("\n}")
    obj = json.loads(text[: cut + 2])
    if "…[truncated" in obj.get("b64", ""):
        raise SystemExit(f"{path}: payload truncated by bridge")
    return obj


def main():
    out = sys.argv[1]
    objs = [load(p) for p in sys.argv[2:]]

    def idx(o):
        m = re.search(r"-(\d+)$", str(o.get("part", "")))
        return int(m.group(1)) if m else 0

    objs.sort(key=idx)
    parts = [idx(o) for o in objs]
    total = objs[0].get("total")
    if total and parts != list(range(total)):
        raise SystemExit(f"missing parts: have {parts}, expected 0..{total-1}")
    b64 = "".join(o["b64"] for o in objs)
    data = gzip.decompress(base64.b64decode(b64))
    with open(out, "wb") as f:
        f.write(data)
    print(f"{out}: {len(objs)} chunks -> {len(data):,} bytes")


if __name__ == "__main__":
    main()
